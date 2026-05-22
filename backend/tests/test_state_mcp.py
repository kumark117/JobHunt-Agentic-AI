"""
Unit tests for the State MCP server tools via the HTTP API layer.
These do not launch a subprocess — they call the state tools through the FastAPI jobs router.
"""
import uuid

import pytest


@pytest.mark.asyncio
async def test_create_and_get_job(client):
    payload = {
        "source": "linkedin",
        "url": f"https://example.com/job/{uuid.uuid4()}",
        "title": "FullStack Architect",
        "company": "Acme Corp",
        "jd_text": "We need a senior architect for our platform team.",
    }
    resp = await client.post("/api/jobs/", json=payload)
    assert resp.status_code == 200
    job = resp.json()
    assert job["title"] == "FullStack Architect"
    assert job["status"] == "discovered"
    assert job["source"] == "linkedin"

    get_resp = await client.get(f"/api/jobs/{job['id']}")
    assert get_resp.status_code == 200
    assert get_resp.json()["company"] == "Acme Corp"


@pytest.mark.asyncio
async def test_list_jobs_filter_by_status(client):
    url = f"https://example.com/job/{uuid.uuid4()}"
    await client.post("/api/jobs/", json={
        "source": "naukri",
        "url": url,
        "title": "AI Engineer",
        "company": "StartupX",
    })

    resp = await client.get("/api/jobs/?status=discovered")
    assert resp.status_code == 200
    jobs = resp.json()
    assert any(j["url"] == url for j in jobs)


@pytest.mark.asyncio
async def test_set_tailor_override(client):
    resp = await client.post("/api/jobs/", json={
        "source": "wellfound",
        "url": f"https://example.com/job/{uuid.uuid4()}",
        "title": "Founding Engineer",
        "company": "YC Startup",
    })
    job_id = resp.json()["id"]

    patch_resp = await client.patch(
        f"/api/jobs/{job_id}/tailor-override",
        json={"tailor_override": "original"},
    )
    assert patch_resp.status_code == 200

    get_resp = await client.get(f"/api/jobs/{job_id}")
    assert get_resp.json()["tailor_override"] == "original"


@pytest.mark.asyncio
async def test_get_job_not_found(client):
    resp = await client.get(f"/api/jobs/{uuid.uuid4()}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_health_endpoint(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
