"""
E2E pipeline test:
  seed job → trigger pipeline → approve all 3 gates → assert status == 'applied'

The pipeline runs as a real asyncio coroutine; HITL gates are resolved programmatically
via hitl_gate.resolve() rather than through HTTP to keep the test deterministic.
Claude calls are mocked so no API key is needed.
"""
import asyncio
import json
import uuid
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from sqlalchemy import select

from db.models import Job
from hitl_gate import hitl_gate, Decision
from pipeline_coordinator import run_pipeline_for_job


MOCK_SCORE = {
    "score": 82,
    "matched": ["React", "FastAPI", "MCP"],
    "gaps": ["Domain knowledge"],
    "red_flags": [],
    "summary": "Strong technical fit.",
    "ats_keywords": ["React", "FastAPI"],
}

MOCK_TAILOR = {
    "sections": [],
    "changed_bullets": [
        {
            "section": "Acme",
            "original": "Built MCP system",
            "tailored": "Architected MCP agent platform",
            "reason": "Aligns with JD framing",
        }
    ],
    "summary": "Senior architect with MCP expertise.",
}

MOCK_OUTREACH = {
    "linkedin_note": {"body": "Hi — strong match for your role.", "char_count": 50},
    "cover_letter": {"subject": "Test", "body": "Dear Hiring Manager,\n\nTest letter.", "word_count": 100},
}


async def _approve_gate(gate: str, job_id: str, delay: float = 0.1, **kwargs):
    await asyncio.sleep(delay)
    decision = Decision(gate=gate, job_id=job_id, decision="approved", **kwargs)
    hitl_gate.resolve(gate, job_id, decision)


@pytest.mark.asyncio
async def test_full_pipeline_all_approved(db_session, sample_jd):
    job = Job(
        source="test",
        url=f"https://test.example.com/job/{uuid.uuid4()}",
        title="Senior FullStack Architect",
        company="TestCo",
        jd_text=sample_jd,
    )
    db_session.add(job)
    await db_session.commit()
    await db_session.refresh(job)
    job_id = str(job.id)

    with (
        patch("pipeline_coordinator.scoring_client.score_fit", AsyncMock(return_value=MOCK_SCORE)),
        patch("pipeline_coordinator.tailor_client.tailor_resume", AsyncMock(return_value=MOCK_TAILOR)),
        patch("pipeline_coordinator.tailor_client.diff_resume", AsyncMock(return_value={"changes": [], "change_count": 1, "added": [], "removed": [], "summary_changed": True})),
        patch("pipeline_coordinator.outreach_client.draft_all", AsyncMock(return_value=MOCK_OUTREACH)),
        patch("pipeline_coordinator.broadcaster.broadcast", AsyncMock()),
        patch("pipeline_coordinator.get_setting", AsyncMock(return_value="always_tailor")),
    ):
        pipeline_task = asyncio.create_task(run_pipeline_for_job(job_id))

        # Approve all three gates with small delays
        await _approve_gate("gate1", job_id, delay=0.05)
        await _approve_gate("gate2", job_id, delay=0.15)
        await _approve_gate("gate3", job_id, delay=0.25)

        await asyncio.wait_for(pipeline_task, timeout=10)

    # Verify final state
    await db_session.refresh(job)
    assert job.status == "applied", f"Expected 'applied', got '{job.status}'"
    assert job.fit_score == 82


@pytest.mark.asyncio
async def test_pipeline_gate1_skip_archives_job(db_session, sample_jd):
    job = Job(
        source="test",
        url=f"https://test.example.com/job/{uuid.uuid4()}",
        title="Junior Dev",
        company="TestCo2",
        jd_text=sample_jd,
    )
    db_session.add(job)
    await db_session.commit()
    await db_session.refresh(job)
    job_id = str(job.id)

    async def skip_gate1(delay=0.05):
        await asyncio.sleep(delay)
        hitl_gate.resolve("gate1", job_id, Decision(gate="gate1", job_id=job_id, decision="skip"))

    with (
        patch("pipeline_coordinator.scoring_client.score_fit", AsyncMock(return_value=MOCK_SCORE)),
        patch("pipeline_coordinator.broadcaster.broadcast", AsyncMock()),
        patch("pipeline_coordinator.get_setting", AsyncMock(return_value="always_tailor")),
    ):
        pipeline_task = asyncio.create_task(run_pipeline_for_job(job_id))
        await skip_gate1()
        await asyncio.wait_for(pipeline_task, timeout=5)

    await db_session.refresh(job)
    assert job.status == "archived"


@pytest.mark.asyncio
async def test_pipeline_gate2_retry_then_approve(db_session, sample_jd):
    job = Job(
        source="test",
        url=f"https://test.example.com/job/{uuid.uuid4()}",
        title="AI Engineer",
        company="TestCo3",
        jd_text=sample_jd,
    )
    db_session.add(job)
    await db_session.commit()
    await db_session.refresh(job)
    job_id = str(job.id)

    gate2_calls = []

    async def handle_gates():
        # Gate 1: approve
        await asyncio.sleep(0.05)
        hitl_gate.resolve("gate1", job_id, Decision(gate="gate1", job_id=job_id, decision="approved"))

        # Gate 2 attempt 1: reject with feedback
        await asyncio.sleep(0.15)
        gate2_calls.append("reject")
        hitl_gate.resolve(
            "gate2", job_id,
            Decision(gate="gate2", job_id=job_id, decision="rejected", feedback="Too generic — emphasise MCP experience")
        )

        # Gate 2 attempt 2: approve
        await asyncio.sleep(0.15)
        gate2_calls.append("approve")
        hitl_gate.resolve("gate2", job_id, Decision(gate="gate2", job_id=job_id, decision="approved"))

        # Gate 3: approve
        await asyncio.sleep(0.1)
        hitl_gate.resolve("gate3", job_id, Decision(gate="gate3", job_id=job_id, decision="approved"))

    with (
        patch("pipeline_coordinator.scoring_client.score_fit", AsyncMock(return_value=MOCK_SCORE)),
        patch("pipeline_coordinator.tailor_client.tailor_resume", AsyncMock(return_value=MOCK_TAILOR)),
        patch("pipeline_coordinator.tailor_client.diff_resume", AsyncMock(return_value={"changes": [], "change_count": 1, "added": [], "removed": [], "summary_changed": False})),
        patch("pipeline_coordinator.outreach_client.draft_all", AsyncMock(return_value=MOCK_OUTREACH)),
        patch("pipeline_coordinator.broadcaster.broadcast", AsyncMock()),
        patch("pipeline_coordinator.get_setting", AsyncMock(return_value="always_tailor")),
    ):
        pipeline_task = asyncio.create_task(run_pipeline_for_job(job_id))
        await asyncio.wait_for(
            asyncio.gather(pipeline_task, handle_gates()),
            timeout=15,
        )

    await db_session.refresh(job)
    assert job.status == "applied"
    assert gate2_calls == ["reject", "approve"]
    assert job.tailor_attempt == 2


@pytest.mark.asyncio
async def test_pipeline_tailor_skipped(db_session, sample_jd):
    job = Job(
        source="test",
        url=f"https://test.example.com/job/{uuid.uuid4()}",
        title="Frontend Lead",
        company="TestCo4",
        jd_text=sample_jd,
        tailor_override="original",
    )
    db_session.add(job)
    await db_session.commit()
    await db_session.refresh(job)
    job_id = str(job.id)

    async def handle_gates():
        await asyncio.sleep(0.05)
        hitl_gate.resolve(
            "gate1", job_id,
            Decision(gate="gate1", job_id=job_id, decision="approved", tailor_choice="original")
        )
        await asyncio.sleep(0.15)
        hitl_gate.resolve("gate3", job_id, Decision(gate="gate3", job_id=job_id, decision="approved"))

    with (
        patch("pipeline_coordinator.scoring_client.score_fit", AsyncMock(return_value=MOCK_SCORE)),
        patch("pipeline_coordinator.outreach_client.draft_all", AsyncMock(return_value=MOCK_OUTREACH)),
        patch("pipeline_coordinator.broadcaster.broadcast", AsyncMock()),
        patch("pipeline_coordinator.get_setting", AsyncMock(return_value="always_tailor")),
    ):
        pipeline_task = asyncio.create_task(run_pipeline_for_job(job_id))
        await asyncio.wait_for(
            asyncio.gather(pipeline_task, handle_gates()),
            timeout=10,
        )

    await db_session.refresh(job)
    assert job.status == "applied"
