import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from db.session import get_db
from db.models import Job, ResumeArtifact, OutreachArtifact, AgentLog, HitlDecision

router = APIRouter()


class JobCreate(BaseModel):
    source: str
    url: str
    title: str
    company: str
    jd_text: Optional[str] = None


class TailorOverrideBody(BaseModel):
    tailor_override: str  # 'tailor' | 'original'


@router.get("/")
async def list_jobs(
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    query = select(Job).order_by(Job.discovered_at.desc())
    if status:
        query = query.where(Job.status == status)
    result = await db.execute(query)
    jobs = result.scalars().all()
    return [_job_dict(j) for j in jobs]


@router.get("/pending")
async def list_pending(db: AsyncSession = Depends(get_db)):
    pending_statuses = ["pending_triage", "pending_resume_review", "pending_apply", "pending_triage_tailor"]
    result = await db.execute(select(Job).where(Job.status.in_(pending_statuses)))
    return [_job_dict(j) for j in result.scalars()]


@router.get("/{job_id}")
async def get_job(job_id: str, db: AsyncSession = Depends(get_db)):
    job = await db.get(Job, uuid.UUID(job_id))
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return _job_dict(job)


@router.get("/{job_id}/resume-artifacts")
async def get_resume_artifacts(job_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(ResumeArtifact)
        .where(ResumeArtifact.job_id == uuid.UUID(job_id))
        .order_by(ResumeArtifact.attempt)
    )
    artifacts = result.scalars().all()
    return [
        {
            "id": str(a.id),
            "attempt": a.attempt,
            "original_json": a.original_json,
            "tailored_json": a.tailored_json,
            "diff_json": a.diff_json,
            "pdf_path": a.pdf_path,
            "created_at": a.created_at.isoformat() if a.created_at else None,
        }
        for a in artifacts
    ]


@router.get("/{job_id}/outreach")
async def get_outreach(job_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(OutreachArtifact)
        .where(OutreachArtifact.job_id == uuid.UUID(job_id))
        .order_by(OutreachArtifact.created_at.desc())
    )
    artifact = result.scalars().first()
    if not artifact:
        raise HTTPException(status_code=404, detail="No outreach drafts found")
    return {
        "id": str(artifact.id),
        "linkedin_note": artifact.linkedin_note,
        "cover_letter": artifact.cover_letter,
        "created_at": artifact.created_at.isoformat() if artifact.created_at else None,
    }


@router.get("/{job_id}/logs")
async def get_logs(job_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(AgentLog)
        .where(AgentLog.job_id == uuid.UUID(job_id))
        .order_by(AgentLog.logged_at)
    )
    return [
        {
            "agent": l.agent,
            "step": l.step,
            "payload": l.payload,
            "logged_at": l.logged_at.isoformat() if l.logged_at else None,
        }
        for l in result.scalars()
    ]


@router.patch("/{job_id}/tailor-override")
async def set_tailor_override(
    job_id: str, body: TailorOverrideBody, db: AsyncSession = Depends(get_db)
):
    job = await db.get(Job, uuid.UUID(job_id))
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    job.tailor_override = body.tailor_override
    await db.commit()
    return {"status": "updated"}


@router.delete("/reset")
async def reset_all_jobs(db: AsyncSession = Depends(get_db)):
    await db.execute(delete(AgentLog))
    await db.execute(delete(ResumeArtifact))
    await db.execute(delete(OutreachArtifact))
    await db.execute(delete(HitlDecision))
    await db.execute(delete(Job))
    await db.commit()
    return {"status": "ok"}


@router.post("/")
async def create_job(body: JobCreate, db: AsyncSession = Depends(get_db)):
    job = Job(
        source=body.source,
        url=body.url,
        title=body.title,
        company=body.company,
        jd_text=body.jd_text,
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)
    return _job_dict(job)


def _job_dict(j: Job) -> dict:
    return {
        "id": str(j.id),
        "source": j.source,
        "url": j.url,
        "title": j.title,
        "company": j.company,
        "jd_text": j.jd_text,
        "fit_score": j.fit_score,
        "fit_summary": j.fit_summary,
        "status": j.status,
        "tailor_attempt": j.tailor_attempt,
        "tailor_override": j.tailor_override,
        "discovered_at": j.discovered_at.isoformat() if j.discovered_at else None,
        "updated_at": j.updated_at.isoformat() if j.updated_at else None,
    }
