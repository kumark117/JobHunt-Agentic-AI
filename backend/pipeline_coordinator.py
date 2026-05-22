"""
Pipeline Coordinator — orchestrates all agents + HITL gates for a single job.
Runs as a background asyncio task per job. Each gate suspends via asyncio.Future.
"""
import asyncio
import json
import logging
import os
import uuid
from pathlib import Path

from dotenv import load_dotenv

from hitl_gate import hitl_gate

logger = logging.getLogger(__name__)
from sse_broadcaster import broadcaster
from mcp_clients.state_client import state_client
from mcp_clients.scoring_client import scoring_client
from mcp_clients.tailor_client import tailor_client
from mcp_clients.outreach_client import outreach_client
from settings_loader import get_setting

load_dotenv()

RESUME_JSON_PATH = Path(__file__).parent / "resume" / "kumar_resume.json"

with open(RESUME_JSON_PATH) as f:
    ORIGINAL_RESUME_JSON = json.load(f)

MAX_RETRIES = int(os.getenv("MAX_TAILOR_RETRIES", "3"))


async def run_pipeline_for_job(job_id: str):
    """Full pipeline: score → Gate 1 → tailor/skip → Gate 2 (optional) → outreach → Gate 3."""
    try:
        job = await state_client.get_pipeline_state(job_id)
        if not job or "error" in job:
            return

        # ── STAGE 1: Score ───────────────────────────────────────────────
        from db.session import AsyncSessionLocal
        from db.models import Job
        from sqlalchemy import update
        import uuid as _uuid

        if job.get("fit_score") is not None:
            # Already scored by discovery cron — skip Claude call
            score_result = job.get("fit_summary") or {"score": job["fit_score"]}
        else:
            await state_client.log_agent_step(job_id, "scoring", "start", {"title": job.get("title")})
            score_result = await scoring_client.score_fit(
                job.get("jd_text", ""), ORIGINAL_RESUME_JSON
            )
            async with AsyncSessionLocal() as session:
                await session.execute(
                    update(Job)
                    .where(Job.id == _uuid.UUID(job_id))
                    .values(
                        fit_score=score_result.get("score"),
                        fit_summary=score_result,
                        status="pending_triage",
                    )
                )
                await session.commit()
            await state_client.log_agent_step(job_id, "scoring", "complete", score_result)

        await broadcaster.broadcast("gate1_ready", job_id, score_result)

        # ── GATE 1: Triage ───────────────────────────────────────────────
        decision1 = await hitl_gate.wait_for_decision("gate1", job_id)
        await state_client.set_hitl_decision(job_id, "gate1", decision1.decision, decision1.feedback)

        if decision1.skip:
            await state_client.update_job_status(job_id, "archived")
            await broadcaster.broadcast("job_archived", job_id, {"gate": "gate1"})
            return

        # Resolve tailor mode
        tailor_mode = await get_setting("tailor_mode", "always_tailor")
        per_job_override = decision1.tailor_choice  # set by UI on Gate 1 card

        skip_tailor = _resolve_tailor(tailor_mode, per_job_override)

        if skip_tailor is None:
            # ask_each_time — wait for tailor decision
            await broadcaster.broadcast("gate1_tailor_question", job_id, {})
            tailor_decision = await hitl_gate.wait_for_decision("gate1_tailor", job_id)
            skip_tailor = tailor_decision.decision == "original"

        await state_client.update_job_status(job_id, "approved_triage")

        # ── STAGE 2: Tailor (or skip) ────────────────────────────────────
        if skip_tailor:
            await state_client.update_job_status(job_id, "tailor_skipped")
            await broadcaster.broadcast("tailor_skipped", job_id, {})
            active_resume = ORIGINAL_RESUME_JSON
        else:
            active_resume = await _run_tailor_stage(job_id, job)
            if active_resume is None:
                return  # max retries exhausted

        # ── STAGE 3: Outreach ────────────────────────────────────────────
        await state_client.update_job_status(job_id, "outreach_drafting")
        await state_client.log_agent_step(job_id, "outreach", "start", {})

        drafts = await outreach_client.draft_all(job, active_resume)

        # Persist outreach artifacts
        from db.models import OutreachArtifact
        async with AsyncSessionLocal() as session:
            artifact = OutreachArtifact(
                job_id=_uuid.UUID(job_id),
                linkedin_note=json.dumps(drafts.get("linkedin_note", {})),
                cover_letter=json.dumps(drafts.get("cover_letter", {})),
            )
            session.add(artifact)
            await session.commit()

        await state_client.update_job_status(job_id, "pending_apply")
        await broadcaster.broadcast("gate3_ready", job_id, drafts)
        await state_client.log_agent_step(job_id, "outreach", "complete", {})

        # ── GATE 3: Apply ────────────────────────────────────────────────
        decision3 = await hitl_gate.wait_for_decision("gate3", job_id)
        await state_client.set_hitl_decision(job_id, "gate3", decision3.decision, decision3.feedback)

        if decision3.skip:
            await state_client.update_job_status(job_id, "archived")
            await broadcaster.broadcast("job_archived", job_id, {"gate": "gate3"})
        else:
            await state_client.update_job_status(job_id, "applied")
            await broadcaster.broadcast("job_applied", job_id, {})

    except asyncio.CancelledError:
        await state_client.update_job_status(job_id, "archived")
        raise
    except Exception as e:
        logger.exception("Pipeline failed for job %s: %s", job_id, e)
        await state_client.log_agent_step(job_id, "pipeline", "error", {"error": str(e)})
        await broadcaster.broadcast("pipeline_error", job_id, {"error": str(e)})


async def _run_tailor_stage(job_id: str, job: dict) -> dict | None:
    from db.session import AsyncSessionLocal
    from db.models import Job, ResumeArtifact
    from sqlalchemy import update
    import uuid as _uuid

    feedback = None
    tailored = None

    for attempt in range(1, MAX_RETRIES + 1):
        await state_client.update_job_status(job_id, "tailoring")
        await state_client.log_agent_step(job_id, "tailor", f"attempt_{attempt}", {"feedback": feedback})

        tailored = await tailor_client.tailor_resume(
            job.get("jd_text", ""), ORIGINAL_RESUME_JSON, feedback=feedback
        )
        diff = await tailor_client.diff_resume(ORIGINAL_RESUME_JSON, tailored)

        async with AsyncSessionLocal() as session:
            artifact = ResumeArtifact(
                job_id=_uuid.UUID(job_id),
                attempt=attempt,
                original_json=ORIGINAL_RESUME_JSON,
                tailored_json=tailored,
                diff_json=diff,
            )
            session.add(artifact)
            await session.execute(
                update(Job).where(Job.id == _uuid.UUID(job_id)).values(tailor_attempt=attempt)
            )
            await session.commit()

        await state_client.update_job_status(job_id, "pending_resume_review")
        await broadcaster.broadcast("gate2_ready", job_id, {"tailored": tailored, "diff": diff, "attempt": attempt})

        # ── GATE 2 ───────────────────────────────────────────────────────
        decision2 = await hitl_gate.wait_for_decision("gate2", job_id)
        await state_client.set_hitl_decision(job_id, "gate2", decision2.decision, decision2.feedback)

        if decision2.approved:
            await state_client.update_job_status(job_id, "resume_approved")
            return tailored

        if decision2.override and decision2.manual_resume:
            await state_client.update_job_status(job_id, "resume_approved")
            return decision2.manual_resume

        if decision2.skip:
            await state_client.update_job_status(job_id, "archived")
            await broadcaster.broadcast("job_archived", job_id, {"gate": "gate2"})
            return None

        feedback = decision2.feedback  # inject into next attempt

    # Max retries exhausted
    await broadcaster.broadcast("gate2_max_retries_reached", job_id, {"attempts": MAX_RETRIES})
    await state_client.update_job_status(job_id, "archived")
    return None


def _resolve_tailor(tailor_mode: str, per_job_override: str | None) -> bool | None:
    if per_job_override == "original":
        return True
    if per_job_override == "tailor":
        return False
    if tailor_mode == "never_tailor":
        return True
    if tailor_mode == "always_tailor":
        return False
    # ask_each_time — caller handles the HITL question
    return None
