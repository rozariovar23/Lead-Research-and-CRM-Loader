import pytest
from httpx import ASGITransport, AsyncClient
from main import app, crm_db

@pytest.fixture
def anyio_backend():
    return 'asyncio'

@pytest.fixture(autouse=True)
async def reset_crm():
    """Reset mock CRM state before each test to ensure test isolation."""
    async with crm_db.lock:
        crm_db.records = {
            "CRMID-881": {
                "domain": "acmesoftware.com",
                "legal_name": "Acme Software Solutions Inc.",
                "region": "North America",
                "employee_count": 250,
            }
        }

@pytest.mark.anyio
async def test_qualified_lead_approved():
    """Test standard qualified lead with user approval and successful post-action verification."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post("/leads/process", json={
            "request_id": "TEST-01",
            "domain": "cloudscale.io",
            "legal_name": "CloudScale Technologies Inc.",
            "region": "North America",
            "employee_count": 180,
            "funding_stage": "Series B",
            "website_active": True,
            "approved": True
        })
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "QUALIFIED"
    assert data["crm_id"] is not None
    assert data["verification_status"] == "VERIFIED_SUCCESS"
    assert "domain" in data["provenance"]
    assert "legal_name" in data["provenance"]

@pytest.mark.anyio
async def test_duplicate_domain_rejected():
    """Test deduplication engine rejecting an existing domain collision."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post("/leads/process", json={
            "request_id": "TEST-02",
            "domain": "acmesoftware.com",  # Already exists in mock CRM fixture
            "legal_name": "Acme Rival Inc.",
            "region": "North America",
            "employee_count": 200,
            "funding_stage": "Series A",
            "website_active": True,
            "approved": True
        })
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "REJECTED"
    assert "Duplicate domain" in data["reason"]
    assert data["crm_id"] is None

@pytest.mark.anyio
async def test_uncertain_lead_missing_evidence():
    """Test missing mandatory evidence resulting in an UNCERTAIN state."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post("/leads/process", json={
            "request_id": "TEST-03",
            "domain": "quantumtech.co",
            "legal_name": "QuantumTech Systems",
            "region": "North America",
            "employee_count": None,  # Missing evidence
            "funding_stage": "Seed",
            "website_active": True,
            "approved": True
        })
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "UNCERTAIN"
    assert "Missing required evidence" in data["reason"]
    assert data["crm_id"] is None

@pytest.mark.anyio
async def test_unapproved_lead():
    """Test qualified lead awaiting human-in-the-loop approval."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post("/leads/process", json={
            "request_id": "TEST-04",
            "domain": "datagrid.io",
            "legal_name": "DataGrid Corp",
            "region": "North America",
            "employee_count": 100,
            "funding_stage": "Series A",
            "website_active": True,
            "approved": False  # Not approved yet
        })
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "QUALIFIED"
    assert data["crm_id"] is None
    assert data["verification_status"] == "PENDING_REVIEW"
