import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, Text, ForeignKey, func, TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


def utcnow():
    return datetime.now(timezone.utc)


class Job(Base):
    __tablename__ = "jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source = Column(String, nullable=False)
    url = Column(Text, unique=True, nullable=False)
    title = Column(Text, nullable=False)
    company = Column(Text, nullable=False)
    jd_text = Column(Text)
    jd_raw_html = Column(Text)
    fit_score = Column(Integer)
    fit_summary = Column(JSONB)
    status = Column(String, nullable=False, default="discovered")
    tailor_attempt = Column(Integer, default=0)
    tailor_override = Column(String)  # NULL | 'tailor' | 'original'
    discovered_at = Column(TIMESTAMP(timezone=True), default=utcnow)
    updated_at = Column(TIMESTAMP(timezone=True), default=utcnow, onupdate=utcnow)

    hitl_decisions = relationship("HitlDecision", back_populates="job", cascade="all, delete-orphan")
    resume_artifacts = relationship("ResumeArtifact", back_populates="job", cascade="all, delete-orphan")
    outreach_artifacts = relationship("OutreachArtifact", back_populates="job", cascade="all, delete-orphan")
    agent_logs = relationship("AgentLog", back_populates="job", cascade="all, delete-orphan")


class HitlDecision(Base):
    __tablename__ = "hitl_decisions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id = Column(UUID(as_uuid=True), ForeignKey("jobs.id"), nullable=False)
    gate = Column(String, nullable=False)      # 'gate1' | 'gate2' | 'gate3'
    decision = Column(String, nullable=False)  # 'approved' | 'rejected' | 'skip' | 'override'
    feedback = Column(Text)
    decided_at = Column(TIMESTAMP(timezone=True), default=utcnow)

    job = relationship("Job", back_populates="hitl_decisions")


class ResumeArtifact(Base):
    __tablename__ = "resume_artifacts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id = Column(UUID(as_uuid=True), ForeignKey("jobs.id"), nullable=False)
    attempt = Column(Integer, nullable=False)
    original_json = Column(JSONB)
    tailored_json = Column(JSONB)
    diff_json = Column(JSONB)
    pdf_path = Column(Text)
    created_at = Column(TIMESTAMP(timezone=True), default=utcnow)

    job = relationship("Job", back_populates="resume_artifacts")


class OutreachArtifact(Base):
    __tablename__ = "outreach_artifacts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id = Column(UUID(as_uuid=True), ForeignKey("jobs.id"), nullable=False)
    linkedin_note = Column(Text)
    cover_letter = Column(Text)
    created_at = Column(TIMESTAMP(timezone=True), default=utcnow)

    job = relationship("Job", back_populates="outreach_artifacts")


class AgentLog(Base):
    __tablename__ = "agent_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id = Column(UUID(as_uuid=True), ForeignKey("jobs.id"), nullable=False)
    agent = Column(String, nullable=False)
    step = Column(String, nullable=False)
    payload = Column(JSONB)
    logged_at = Column(TIMESTAMP(timezone=True), default=utcnow)

    job = relationship("Job", back_populates="agent_logs")


class Setting(Base):
    __tablename__ = "settings"

    key = Column(String, primary_key=True)
    value = Column(Text, nullable=False)
    updated_at = Column(TIMESTAMP(timezone=True), default=utcnow, onupdate=utcnow)
