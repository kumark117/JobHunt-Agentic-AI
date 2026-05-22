"""Initial schema

Revision ID: 001
Revises:
Create Date: 2026-05-22

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "jobs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("url", sa.Text(), nullable=False, unique=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("company", sa.Text(), nullable=False),
        sa.Column("jd_text", sa.Text()),
        sa.Column("jd_raw_html", sa.Text()),
        sa.Column("fit_score", sa.Integer()),
        sa.Column("fit_summary", JSONB()),
        sa.Column("status", sa.String(), nullable=False, server_default="discovered"),
        sa.Column("tailor_attempt", sa.Integer(), server_default="0"),
        sa.Column("tailor_override", sa.String()),
        sa.Column("discovered_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()")),
    )

    op.create_table(
        "hitl_decisions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("job_id", UUID(as_uuid=True), sa.ForeignKey("jobs.id"), nullable=False),
        sa.Column("gate", sa.String(), nullable=False),
        sa.Column("decision", sa.String(), nullable=False),
        sa.Column("feedback", sa.Text()),
        sa.Column("decided_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()")),
    )

    op.create_table(
        "resume_artifacts",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("job_id", UUID(as_uuid=True), sa.ForeignKey("jobs.id"), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False),
        sa.Column("original_json", JSONB()),
        sa.Column("tailored_json", JSONB()),
        sa.Column("diff_json", JSONB()),
        sa.Column("pdf_path", sa.Text()),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()")),
    )

    op.create_table(
        "outreach_artifacts",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("job_id", UUID(as_uuid=True), sa.ForeignKey("jobs.id"), nullable=False),
        sa.Column("linkedin_note", sa.Text()),
        sa.Column("cover_letter", sa.Text()),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()")),
    )

    op.create_table(
        "agent_logs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("job_id", UUID(as_uuid=True), sa.ForeignKey("jobs.id"), nullable=False),
        sa.Column("agent", sa.String(), nullable=False),
        sa.Column("step", sa.String(), nullable=False),
        sa.Column("payload", JSONB()),
        sa.Column("logged_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()")),
    )

    op.create_table(
        "settings",
        sa.Column("key", sa.String(), primary_key=True),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()")),
    )

    # Seed default settings
    op.execute("INSERT INTO settings VALUES ('tailor_mode', 'always_tailor', now())")
    op.execute("INSERT INTO settings VALUES ('fit_score_threshold', '65', now())")
    op.execute("INSERT INTO settings VALUES ('max_tailor_retries', '3', now())")


def downgrade() -> None:
    op.drop_table("agent_logs")
    op.drop_table("outreach_artifacts")
    op.drop_table("resume_artifacts")
    op.drop_table("hitl_decisions")
    op.drop_table("settings")
    op.drop_table("jobs")
