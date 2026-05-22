import asyncio
import logging
import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from db.session import engine
from db.models import Base
from routers import jobs, pipeline, settings as settings_router
from middleware.auth import APIKeyMiddleware

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)


logger = logging.getLogger(__name__)


async def _resume_orphaned_pipelines():
    """Restart pipeline coroutines for jobs stuck at a gate after a server restart."""
    from db.session import AsyncSessionLocal
    from db.models import Job
    from sqlalchemy import select
    from pipeline_coordinator import run_pipeline_for_job

    gate_waiting = ["pending_triage", "pending_resume_review", "pending_apply"]
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Job).where(Job.status.in_(gate_waiting)))
        orphans = result.scalars().all()

    for job in orphans:
        logger.info("Resuming pipeline for orphaned job %s (%s)", job.id, job.status)
        asyncio.create_task(run_pipeline_for_job(str(job.id)))


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    await _resume_orphaned_pipelines()

    # Start APScheduler cron (skip in test environments)
    if os.getenv("ENABLE_CRON", "true").lower() == "true":
        from cron_scheduler import create_scheduler
        scheduler = create_scheduler()
        scheduler.start()
        app.state.scheduler = scheduler

    yield

    if hasattr(app.state, "scheduler"):
        app.state.scheduler.shutdown(wait=False)

    await engine.dispose()


app = FastAPI(title="JobHunt Agent API", version="1.0.0", lifespan=lifespan)

app.add_middleware(APIKeyMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", os.getenv("FRONTEND_URL", "")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*", "X-API-Key"],
)

app.include_router(jobs.router, prefix="/api/jobs", tags=["jobs"])
app.include_router(pipeline.router, prefix="/api/pipeline", tags=["pipeline"])
app.include_router(settings_router.router, prefix="/api/settings", tags=["settings"])


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/version")
async def version():
    return {"api_version": "1.0.0"}
