import asyncio
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from hitl_gate import hitl_gate, Decision
from sse_broadcaster import broadcaster
from pipeline_coordinator import run_pipeline_for_job
from middleware.rate_limiter import check_pipeline_cooldown

router = APIRouter()

_discovery_running = False


class DecisionBody(BaseModel):
    decision: str                       # 'approved' | 'rejected' | 'skip' | 'override'
    feedback: Optional[str] = None
    manual_resume: Optional[dict] = None
    tailor_choice: Optional[str] = None  # for gate1 tailor question


@router.post("/run-discovery")
async def trigger_discovery(background_tasks: BackgroundTasks):
    global _discovery_running
    if _discovery_running:
        raise HTTPException(status_code=409, detail="Discovery is already running.")
    from cron_scheduler import run_discovery_and_queue

    async def _run():
        global _discovery_running
        _discovery_running = True
        try:
            await run_discovery_and_queue()
        finally:
            _discovery_running = False

    background_tasks.add_task(_run)
    return {"status": "started"}


@router.get("/discovery-status")
async def discovery_status():
    return {"running": _discovery_running}


@router.get("/debug-discovery")
async def debug_discovery():
    import os
    from mcp_clients.discovery_client import DiscoveryClient
    client = DiscoveryClient()
    mock_env = os.getenv("MOCK_DISCOVERY", "NOT_SET")
    try:
        raw = await client.call_tool("search_jobs", {"keywords": ["AI Engineer"], "location": "Bangalore", "days_back": 1})
        return {"MOCK_DISCOVERY_env": mock_env, "result_type": type(raw).__name__, "result": raw}
    except Exception as e:
        return {"MOCK_DISCOVERY_env": mock_env, "error": str(e)}


@router.post("/run/{job_id}")
async def trigger_pipeline(job_id: str, background_tasks: BackgroundTasks):
    allowed, retry_after = check_pipeline_cooldown(job_id)
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail=f"Pipeline for this job was triggered recently. Retry after {retry_after}s.",
        )
    background_tasks.add_task(run_pipeline_for_job, job_id)
    return {"status": "started", "job_id": job_id}


@router.post("/hitl/{gate}/{job_id}")
async def submit_hitl_decision(gate: str, job_id: str, body: DecisionBody):
    decision = Decision(
        gate=gate,
        job_id=job_id,
        decision=body.decision,
        feedback=body.feedback,
        manual_resume=body.manual_resume,
        tailor_choice=body.tailor_choice,
    )
    resolved = hitl_gate.resolve(gate, job_id, decision)

    if not resolved:
        # Pipeline not running (server restart / first time) — start it and wait for gate
        from pipeline_coordinator import run_pipeline_for_job
        asyncio.create_task(run_pipeline_for_job(job_id))
        for _ in range(20):          # up to 10 s
            await asyncio.sleep(0.5)
            resolved = hitl_gate.resolve(gate, job_id, decision)
            if resolved:
                break

    if not resolved:
        raise HTTPException(
            status_code=409,
            detail=f"Pipeline for job '{job_id}' did not reach '{gate}' in time. Check logs.",
        )
    return {"status": "ok", "gate": gate, "decision": body.decision}


@router.get("/pending-gates")
async def list_pending_gates():
    return {"pending": hitl_gate.list_pending()}


@router.get("/sse")
async def sse_stream():
    q = broadcaster.subscribe()

    async def event_generator():
        try:
            while True:
                async for chunk in broadcaster.stream(q):
                    yield chunk
        finally:
            broadcaster.unsubscribe(q)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
