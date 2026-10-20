from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field
from typing import Optional, Dict
from enum import Enum
from datetime import datetime, timezone
import hashlib
import asyncio

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
        self.records: Dict[str, dict] = {
            "CRMID-881": {
                "domain": "acmesoftware.com",
                "legal_name": "Acme Software Solutions Inc.",
                "region": "North America",
                "employee_count": 250,
            }
        }
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
                    return crm_id
            
            new_id = f"CRMID-{len(self.records) + 100}"
            payload["idempotency_key"] = idempotency_key
            self.records[new_id] = payload
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

        # 1. Deduplication checks with Idempotent Retry Handling
        existing_domain = await self.db.find_by_domain(lead.domain)
        if existing_domain:
            async with self.db.lock:
                is_idempotent = self.db.records.get(existing_domain, {}).get("idempotency_key") == idempotency_key
            
            if is_idempotent:
                record_check = await self.db.get_record(existing_domain)
                verif = VerificationStateEnum.VERIFIED_SUCCESS if (record_check and lead.website_active) else VerificationStateEnum.FAILED
                return DecisionResponseSchema(
                    lead_id=lead.request_id,
                    status=StatusEnum.QUALIFIED,
                    reason="Passed all qualification criteria. [Idempotency Guard: Re-execution detected, duplicate mutation prevented].",
                    provenance=provenance,
                    idempotency_key=idempotency_key,
                    verification_status=verif,
                    crm_id=existing_domain
                )

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

@app.post("/leads/process", response_model=DecisionResponseSchema, status_code=status.HTTP_200_OK)
async def process_lead(lead: LeadInputSchema):
    """Asynchronous endpoint to evaluate, deduplicate, load, and verify a lead record."""
    try:
        result = await agent_service.evaluate_and_load(lead)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
