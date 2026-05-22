"""
Cron scheduler — APScheduler-based daily discovery runner.
Registered in FastAPI lifespan so it runs alongside the web server.
Alternatively, use Render cron jobs calling cron_runner.py directly.
"""
import asyncio
import json
import logging
import os
import uuid
from pathlib import Path
from pipeline_coordinator import run_pipeline_for_job

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from mcp_clients.discovery_client import DiscoveryClient
from mcp_clients.scoring_client import ScoringClient
from settings_loader import get_setting

logger = logging.getLogger(__name__)

RESUME_JSON_PATH = Path(__file__).parent / "resume" / "kumar_resume.json"

with open(RESUME_JSON_PATH) as f:
    RESUME_JSON = json.load(f)


async def run_discovery_and_queue():
    """
    Daily job: discover new listings, score them, and insert
    qualifying jobs (score >= threshold) as pending_triage records.
    """
    logger.info("Daily discovery starting")

    from db.session import AsyncSessionLocal
    from db.models import Job
    from sqlalchemy import select

    discovery = DiscoveryClient()
    scoring = ScoringClient()

    target_roles = await get_setting("target_roles", ["FullStack Architect", "AI Engineer"])
    target_locations = await get_setting("target_locations", ["Bangalore", "Remote"])
    threshold = int(await get_setting("fit_score_threshold", "65"))
    discovery_sources_raw = await get_setting("discovery_sources", "{}")

    if isinstance(target_roles, str):
        import json as _json
        target_roles = _json.loads(target_roles)
    if isinstance(target_locations, str):
        import json as _json
        target_locations = _json.loads(target_locations)

    location = target_locations[0] if target_locations else "Bangalore"
    keywords = target_roles[:4]

    try:
        listings = await discovery.search_jobs(keywords=keywords, location=location, days_back=1)
    except Exception as e:
        logger.error("Discovery failed: %s", e)
        return

    logger.info("Discovered %d listings", len(listings))

    queued_job_ids: list[str] = []

    async with AsyncSessionLocal() as session:
        for listing in listings:
            url = listing.get("url", "")
            if not url:
                continue

            # Skip already-known URLs
            existing = await session.execute(select(Job).where(Job.url == url))
            if existing.scalars().first():
                continue

            # Fetch full JD
            try:
                jd_data = await discovery.fetch_jd_full(url)
                jd_text = jd_data.get("jd_text", listing.get("snippet", ""))
            except Exception:
                jd_text = listing.get("snippet", "")

            if not jd_text:
                continue

            # Score against resume
            try:
                score_result = await scoring.score_fit(jd_text, RESUME_JSON)
                score = score_result.get("score", 0)
            except Exception as e:
                logger.warning("Scoring failed for %s: %s", url, e)
                continue

            # Only persist if it meets the threshold
            if score < threshold:
                logger.debug("Skipping %s (score %d < %d)", url, score, threshold)
                continue

            job = Job(
                source=listing.get("source", "unknown"),
                url=url,
                title=listing.get("title", "Untitled"),
                company=listing.get("company", "Unknown"),
                jd_text=jd_text,
                fit_score=score,
                fit_summary=score_result,
                status="pending_triage",
            )
            session.add(job)
            queued_job_ids.append(str(job.id))
            logger.info("Queued: %s at %s (score %d)", job.title, job.company, score)

        await session.commit()

    # Start pipeline for each queued job so Gate 1 futures are registered
    for job_id in queued_job_ids:
        asyncio.create_task(run_pipeline_for_job(job_id))

    logger.info("Daily discovery complete")


def create_scheduler() -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone="Asia/Kolkata")
    scheduler.add_job(
        run_discovery_and_queue,
        CronTrigger.from_crontab(
            os.getenv("DISCOVERY_CRON", "0 8 * * *"),
            timezone="Asia/Kolkata",
        ),
        id="daily_discovery",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    return scheduler
