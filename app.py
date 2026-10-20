import os
import asyncio
import hashlib
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, Optional, List, Any
from fastapi import FastAPI, HTTPException, status
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

app = FastAPI(
    title="Lead Research & CRM Loader Agent API",
    version="1.0.0",
    description="Asynchronous agent service for lead qualification, deduplication, and CRM loading."
)

# Enums
class StatusEnum(str, Enum):
    QUALIFIED = "QUALIFIED"
    REJECTED = "REJECTED"
    UNCERTAIN = "UNCERTAIN"

class VerificationStateEnum(str, Enum):
    VERIFIED_SUCCESS = "VERIFIED_SUCCESS"
    PENDING = "PENDING_REVIEW"
    FAILED = "FAILED"
    NOT_APPLICABLE = "N/A"

# Pydantic Schemas
class LeadInputSchema(BaseModel):
    request_id: str = Field(..., examples=["REQ-2026-001"])
    domain: str = Field(..., examples=["cloudscale.io"])
    legal_name: str = Field(..., examples=["CloudScale Technologies Inc."])
    region: str = Field(..., examples=["North America"])
    employee_count: Optional[int] = Field(None, examples=[180])
    funding_stage: str = Field(..., examples=["Series B"])
    industry: Optional[str] = Field("Enterprise Software", examples=["Enterprise Software"])
    website_active: bool = Field(True, examples=[True])
    approved: bool = Field(False, examples=[True])

class ProvenanceSchema(BaseModel):
    source_url: str
    extracted_at: str
    raw_value: str

class DecisionResponseSchema(BaseModel):
    lead_id: str
    status: StatusEnum
    reason: str
    provenance: Dict[str, ProvenanceSchema]
    idempotency_key: str
    verification_status: VerificationStateEnum
    crm_id: Optional[str] = None

# Mock CRM Database with Async locks
class AsyncMockCRMDatabase:
    def __init__(self):
        self.view_name = "Private Research Leads (Sandbox View ID: HS-PRIV-VIEW-409)"
        self.records: Dict[str, dict] = {
            "CRMID-881": {
                "domain": "acmesoftware.com",
                "legal_name": "Acme Software Solutions Inc.",
                "region": "North America",
                "employee_count": 250,
                "industry": "Enterprise Software",
                "funding_stage": "Series A",
                "idempotency_key": "seed-acme-881",
                "private_view": self.view_name,
                "created_at": "2026-01-10T10:00:00Z"
            }
        }
        self.audit_log: List[dict] = []
        self.lock = asyncio.Lock()

    async def find_by_domain(self, domain: str) -> Optional[str]:
        async with self.lock:
            for crm_id, data in self.records.items():
                if data["domain"].lower() == domain.lower():
                    return crm_id
            return None

    async def find_by_legal_name(self, name: str) -> Optional[str]:
        async with self.lock:
            for crm_id, data in self.records.items():
                if name.lower() in data["legal_name"].lower():
                    return crm_id
            return None

    async def insert_record(self, idempotency_key: str, payload: dict) -> str:
        async with self.lock:
            for crm_id, data in self.records.items():
                if data.get("idempotency_key") == idempotency_key:
                    self.audit_log.append({
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "action": "DUPLICATE_EXECUTION_PREVENTED",
                        "crm_id": crm_id,
                        "idempotency_key": idempotency_key,
                        "note": f"Idempotent retry detected. Returned existing record {crm_id} with zero duplicate creation."
                    })
                    return crm_id
            
            new_id = f"CRMID-{len(self.records) + 100}"
            payload["idempotency_key"] = idempotency_key
            payload["private_view"] = self.view_name
            payload["created_at"] = datetime.now(timezone.utc).isoformat()
            self.records[new_id] = payload
            self.audit_log.append({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "action": "NEW_RECORD_INSERTED",
                "crm_id": new_id,
                "idempotency_key": idempotency_key,
                "note": f"Successfully inserted lead into {self.view_name}"
            })
            return new_id

    async def get_record(self, crm_id: str) -> Optional[dict]:
        async with self.lock:
            return self.records.get(crm_id)

crm_db = AsyncMockCRMDatabase()

# Agent Service Logic
class AsyncLeadAgentService:
    def __init__(self, db: AsyncMockCRMDatabase):
        self.db = db
        self.min_employees = 50
        self.max_employees = 500
        self.allowed_regions = ["north america", "us", "ca", "canada", "usa"]

    async def evaluate_and_load(self, lead: LeadInputSchema) -> DecisionResponseSchema:
        timestamp = datetime.now(timezone.utc).isoformat()
        provenance = {
            "domain": ProvenanceSchema(source_url=f"https://{lead.domain}", extracted_at=timestamp, raw_value=lead.domain),
            "legal_name": ProvenanceSchema(source_url=f"https://directory.example.com/{lead.domain}", extracted_at=timestamp, raw_value=lead.legal_name)
        }

        # Idempotency Key Generation
        raw_key = f"{lead.request_id}-{lead.domain}-{lead.legal_name}"
        idempotency_key = hashlib.sha256(raw_key.encode()).hexdigest()

        # Check if this exact request was already inserted (idempotent retry check)
        async with self.db.lock:
            existing_idemp_crm_id = None
            for c_id, d in self.db.records.items():
                if d.get("idempotency_key") == idempotency_key:
                    existing_idemp_crm_id = c_id
                    break

        if existing_idemp_crm_id:
            record_check = await self.db.get_record(existing_idemp_crm_id)
            verif = VerificationStateEnum.VERIFIED_SUCCESS if (record_check and lead.website_active) else VerificationStateEnum.FAILED
            return DecisionResponseSchema(
                lead_id=lead.request_id,
                status=StatusEnum.QUALIFIED,
                reason=f"Passed all qualification criteria. [Idempotency Guard: Re-execution intercepted. Returned existing record {existing_idemp_crm_id}].",
                provenance=provenance,
                idempotency_key=idempotency_key,
                verification_status=verif,
                crm_id=existing_idemp_crm_id
            )

        # 1. Deduplication checks
        existing_domain = await self.db.find_by_domain(lead.domain)
        if existing_domain:
            return DecisionResponseSchema(
                lead_id=lead.request_id,
                status=StatusEnum.REJECTED,
                reason=f"Duplicate domain matched existing record {existing_domain}",
                provenance=provenance,
                idempotency_key=idempotency_key,
                verification_status=VerificationStateEnum.NOT_APPLICABLE
            )

        existing_name = await self.db.find_by_legal_name(lead.legal_name)
        if existing_name:
            return DecisionResponseSchema(
                lead_id=lead.request_id,
                status=StatusEnum.REJECTED,
                reason=f"Duplicate legal name matched existing record {existing_name}",
                provenance=provenance,
                idempotency_key=idempotency_key,
                verification_status=VerificationStateEnum.NOT_APPLICABLE
            )

        # 2. Missing Evidence Check (Uncertain State)
        if lead.employee_count is None:
            return DecisionResponseSchema(
                lead_id=lead.request_id,
                status=StatusEnum.UNCERTAIN,
                reason="Missing required evidence: employee count could not be verified.",
                provenance=provenance,
                idempotency_key=idempotency_key,
                verification_status=VerificationStateEnum.NOT_APPLICABLE
            )

        # 3. Qualification Rules
        if lead.region.lower() not in self.allowed_regions:
            return DecisionResponseSchema(
                lead_id=lead.request_id,
                status=StatusEnum.REJECTED,
                reason=f"Region '{lead.region}' outside target scope.",
                provenance=provenance,
                idempotency_key=idempotency_key,
                verification_status=VerificationStateEnum.NOT_APPLICABLE
            )

        if not (self.min_employees <= lead.employee_count <= self.max_employees):
            return DecisionResponseSchema(
                lead_id=lead.request_id,
                status=StatusEnum.REJECTED,
                reason=f"Employee count ({lead.employee_count}) outside permitted range [{self.min_employees}-{self.max_employees}].",
                provenance=provenance,
                idempotency_key=idempotency_key,
                verification_status=VerificationStateEnum.NOT_APPLICABLE
            )

        # 4. Action Execution (If Approved)
        crm_id = None
        verification_status = VerificationStateEnum.NOT_APPLICABLE

        if lead.approved:
            payload = {
                "domain": lead.domain,
                "legal_name": lead.legal_name,
                "region": lead.region,
                "employee_count": lead.employee_count,
                "industry": lead.industry,
                "funding_stage": lead.funding_stage
            }
            crm_id = await self.db.insert_record(idempotency_key, payload)

            # 5. Verification Phase
            record_check = await self.db.get_record(crm_id)
            if record_check and lead.website_active:
                verification_status = VerificationStateEnum.VERIFIED_SUCCESS
            elif record_check and not lead.website_active:
                verification_status = VerificationStateEnum.FAILED
            else:
                verification_status = VerificationStateEnum.PENDING
        else:
            verification_status = VerificationStateEnum.PENDING

        reason_text = "Passed all qualification criteria." if lead.approved else "Qualified, but pending user approval."

        return DecisionResponseSchema(
            lead_id=lead.request_id,
            status=StatusEnum.QUALIFIED,
            reason=reason_text,
            provenance=provenance,
            idempotency_key=idempotency_key,
            verification_status=verification_status,
            crm_id=crm_id
        )

agent_service = AsyncLeadAgentService(crm_db)

# Primary Endpoint as defined by user
@app.post("/leads/process", response_model=DecisionResponseSchema, status_code=status.HTTP_200_OK)
async def process_lead(lead: LeadInputSchema):
    """Asynchronous endpoint to evaluate, deduplicate, load, and verify a lead record."""
    try:
        result = await agent_service.evaluate_and_load(lead)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Benchmark Scenarios Definition
OFFICIAL_BENCHMARK_SCENARIOS = [
    {
        "label": "RUN-01",
        "name": "CloudScale Technologies Inc.",
        "payload": LeadInputSchema(
            request_id="RUN-01",
            domain="cloudscale.io",
            legal_name="CloudScale Technologies Inc.",
            region="North America",
            employee_count=180,
            funding_stage="Series B",
            industry="Cloud Infrastructure",
            website_active=True,
            approved=True
        ),
        "expected_status": StatusEnum.QUALIFIED,
        "expected_verification": VerificationStateEnum.VERIFIED_SUCCESS,
        "description": "Standard ideal B2B prospect within region & size range; website resolves HTTP 200."
    },
    {
        "label": "RUN-02",
        "name": "Acme Software Solutions Inc.",
        "payload": LeadInputSchema(
            request_id="RUN-02",
            domain="acmesoftware.com",
            legal_name="Acme Software Solutions Inc.",
            region="North America",
            employee_count=250,
            funding_stage="Series A",
            industry="Enterprise Software",
            website_active=True,
            approved=True
        ),
        "expected_status": StatusEnum.REJECTED,
        "expected_verification": VerificationStateEnum.NOT_APPLICABLE,
        "description": "Deduplication collision against existing CRM record CRMID-881 (domain & legal name match)."
    },
    {
        "label": "RUN-03",
        "name": "QuantumTech Systems",
        "payload": LeadInputSchema(
            request_id="RUN-03",
            domain="quantumtech.co",
            legal_name="QuantumTech Systems",
            region="North America",
            employee_count=None,
            funding_stage="Seed",
            industry="Artificial Intelligence",
            website_active=True,
            approved=True
        ),
        "expected_status": StatusEnum.UNCERTAIN,
        "expected_verification": VerificationStateEnum.NOT_APPLICABLE,
        "description": "Missing required public evidence for employee count -> triggers UNCERTAIN state."
    },
    {
        "label": "RUN-04",
        "name": "GhostCorp Industries",
        "payload": LeadInputSchema(
            request_id="RUN-04",
            domain="ghostcorp-test.com",
            legal_name="GhostCorp Industries",
            region="Canada",
            employee_count=75,
            funding_stage="Bootstrapped",
            industry="Enterprise Software",
            website_active=False,
            approved=True
        ),
        "expected_status": StatusEnum.QUALIFIED,
        "expected_verification": VerificationStateEnum.FAILED,
        "description": "Passed qualification & inserted into CRM, but post-action resolution catches inactive website (HTTP 404)."
    }
]

@app.get("/api/scenarios")
async def get_scenarios():
    return [
        {
            "label": sc["label"],
            "name": sc["name"],
            "description": sc["description"],
            "expected_status": sc["expected_status"].value,
            "expected_verification": sc["expected_verification"].value,
            "data": sc["payload"].model_dump()
        }
        for sc in OFFICIAL_BENCHMARK_SCENARIOS
    ]

@app.post("/api/run-all-official")
async def run_all_official_scenarios():
    """Runs all 4 official benchmark runs + idempotency retry run using process_lead."""
    results = []

    for sc in OFFICIAL_BENCHMARK_SCENARIOS:
        dec = await agent_service.evaluate_and_load(sc["payload"])
        status_match = dec.status == sc["expected_status"]
        verif_match = dec.verification_status == sc["expected_verification"]

        results.append({
            "scenario": {
                "label": sc["label"],
                "name": sc["name"],
                "domain": sc["payload"].domain,
                "region": sc["payload"].region,
                "employee_count": sc["payload"].employee_count,
                "website_active": sc["payload"].website_active,
                "description": sc["description"],
                "expected_status": sc["expected_status"].value,
                "expected_verification": sc["expected_verification"].value
            },
            "decision": dec.model_dump(),
            "status_match": status_match,
            "verification_match": verif_match
        })

    # Test Idempotency Retry on RUN-01
    run01_payload = OFFICIAL_BENCHMARK_SCENARIOS[0]["payload"]
    retry_dec = await agent_service.evaluate_and_load(run01_payload)
    idempotency_run = {
        "label": "RUN-01-RETRY",
        "description": "Re-executing RUN-01 with exact same parameters to verify duplicate execution prevention.",
        "crm_id": retry_dec.crm_id,
        "is_prevented": "Idempotency Guard" in retry_dec.reason,
        "decision": retry_dec.model_dump()
    }

    # Step 6 Result View aggregation
    qualified_leads = []
    rejected_leads = []
    unresolved_leads = []

    for r in results:
        sc = r["scenario"]
        dec = r["decision"]
        trace = {
            "request_id": dec["lead_id"],
            "domain": sc["domain"],
            "legal_name": sc["name"],
            "region": sc["region"],
            "employee_count": sc["employee_count"],
            "status": dec["status"],
            "decision_reason": dec["reason"],
            "sources": dec["provenance"],
            "crm_id": dec.get("crm_id"),
            "verification_status": dec["verification_status"],
            "target_view": crm_db.view_name
        }
        if dec["status"] == StatusEnum.QUALIFIED.value:
            qualified_leads.append(trace)
        elif dec["status"] == StatusEnum.REJECTED.value:
            rejected_leads.append(trace)
        elif dec["status"] == StatusEnum.UNCERTAIN.value:
            trace["missing_items"] = ["employee_count (Null)"]
            unresolved_leads.append(trace)

    return {
        "benchmark_runs": results,
        "idempotency_test": idempotency_run,
        "step6_result_view": {
            "summary": {
                "total_processed": len(results),
                "qualified_count": len(qualified_leads),
                "rejected_count": len(rejected_leads),
                "unresolved_count": len(unresolved_leads)
            },
            "qualified_leads_view": qualified_leads,
            "rejected_leads_view": rejected_leads,
            "unresolved_leads_view": unresolved_leads
        },
        "crm_state": {
            "records": crm_db.records,
            "audit_log": crm_db.audit_log
        }
    }

@app.get("/api/crm-records")
async def get_crm_records():
    return {
        "view_name": crm_db.view_name,
        "total_records": len(crm_db.records),
        "records": crm_db.records,
        "audit_log": crm_db.audit_log
    }

@app.post("/api/reset-crm")
async def reset_crm():
    global crm_db, agent_service
    crm_db = AsyncMockCRMDatabase()
    agent_service = AsyncLeadAgentService(crm_db)
    return {"message": "CRM database successfully reset to clean initial seed."}

# Static Mount for Web UI
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/")
async def root():
    index_file = os.path.join(static_dir, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return {"message": "Lead Research & CRM Loader API is active. Visit /docs for OpenAPI specs."}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=False)
