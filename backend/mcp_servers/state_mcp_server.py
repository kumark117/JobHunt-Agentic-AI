"""
M1 — State MCP Server
Provides CRUD over job pipeline state in PostgreSQL.
Launched as a subprocess by FastAPI via stdio transport.
"""
import asyncio
import json
import os
import sys
import uuid
from datetime import datetime, timezone

from dotenv import load_dotenv
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

load_dotenv()

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:password@localhost:5432/jobhunt",
)

engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

# Import models inline so the server is self-contained
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from db.models import Job, HitlDecision, AgentLog, Setting

server = Server("state-server")


@server.list_tools()
async def list_tools():
    return [
        Tool(
            name="get_pipeline_state",
            description="Get full job record with status, fit score, and decision history",
            inputSchema={
                "type": "object",
                "properties": {"job_id": {"type": "string"}},
                "required": ["job_id"],
            },
        ),
        Tool(
            name="set_hitl_decision",
            description="Record a human HITL decision for a gate and advance job status",
            inputSchema={
                "type": "object",
                "properties": {
                    "job_id": {"type": "string"},
                    "gate": {"type": "string", "enum": ["gate1", "gate2", "gate3"]},
                    "decision": {"type": "string", "enum": ["approved", "rejected", "skip", "override"]},
                    "feedback": {"type": "string"},
                },
                "required": ["job_id", "gate", "decision"],
            },
        ),
        Tool(
            name="list_pending_approvals",
            description="List jobs awaiting human action, optionally filtered by gate",
            inputSchema={
                "type": "object",
                "properties": {"gate": {"type": "string"}},
            },
        ),
        Tool(
            name="update_job_status",
            description="Update a job's pipeline status and optional notes",
            inputSchema={
                "type": "object",
                "properties": {
                    "job_id": {"type": "string"},
                    "status": {"type": "string"},
                    "notes": {"type": "string"},
                },
                "required": ["job_id", "status"],
            },
        ),
        Tool(
            name="log_agent_step",
            description="Append a ReAct step trace entry for a job",
            inputSchema={
                "type": "object",
                "properties": {
                    "job_id": {"type": "string"},
                    "agent": {"type": "string"},
                    "step": {"type": "string"},
                    "payload": {"type": "object"},
                },
                "required": ["job_id", "agent", "step"],
            },
        ),
    ]


def _serialize_job(job: Job) -> dict:
    return {
        "id": str(job.id),
        "source": job.source,
        "url": job.url,
        "title": job.title,
        "company": job.company,
        "fit_score": job.fit_score,
        "fit_summary": job.fit_summary,
        "status": job.status,
        "tailor_attempt": job.tailor_attempt,
        "tailor_override": job.tailor_override,
        "discovered_at": job.discovered_at.isoformat() if job.discovered_at else None,
        "updated_at": job.updated_at.isoformat() if job.updated_at else None,
    }


@server.call_tool()
async def call_tool(name: str, arguments: dict):
    async with AsyncSessionLocal() as session:
        match name:
            case "get_pipeline_state":
                result = await session.get(Job, uuid.UUID(arguments["job_id"]))
                if not result:
                    return [TextContent(type="text", text=json.dumps({"error": "Job not found"}))]
                decisions = await session.execute(
                    select(HitlDecision).where(HitlDecision.job_id == result.id)
                )
                history = [
                    {
                        "gate": d.gate,
                        "decision": d.decision,
                        "feedback": d.feedback,
                        "decided_at": d.decided_at.isoformat() if d.decided_at else None,
                    }
                    for d in decisions.scalars()
                ]
                data = _serialize_job(result)
                data["decision_history"] = history
                return [TextContent(type="text", text=json.dumps(data))]

            case "set_hitl_decision":
                decision = HitlDecision(
                    job_id=uuid.UUID(arguments["job_id"]),
                    gate=arguments["gate"],
                    decision=arguments["decision"],
                    feedback=arguments.get("feedback"),
                )
                session.add(decision)
                await session.commit()
                return [TextContent(type="text", text=json.dumps({"status": "recorded"}))]

            case "list_pending_approvals":
                pending_statuses = ["pending_triage", "pending_resume_review", "pending_apply", "pending_triage_tailor"]
                gate_filter = arguments.get("gate")
                if gate_filter == "gate1":
                    statuses = ["pending_triage", "pending_triage_tailor"]
                elif gate_filter == "gate2":
                    statuses = ["pending_resume_review"]
                elif gate_filter == "gate3":
                    statuses = ["pending_apply"]
                else:
                    statuses = pending_statuses
                result = await session.execute(select(Job).where(Job.status.in_(statuses)))
                jobs = [_serialize_job(j) for j in result.scalars()]
                return [TextContent(type="text", text=json.dumps(jobs))]

            case "update_job_status":
                await session.execute(
                    update(Job)
                    .where(Job.id == uuid.UUID(arguments["job_id"]))
                    .values(
                        status=arguments["status"],
                        updated_at=datetime.now(timezone.utc),
                    )
                )
                await session.commit()
                return [TextContent(type="text", text=json.dumps({"status": "updated"}))]

            case "log_agent_step":
                log = AgentLog(
                    job_id=uuid.UUID(arguments["job_id"]),
                    agent=arguments["agent"],
                    step=arguments["step"],
                    payload=arguments.get("payload"),
                )
                session.add(log)
                await session.commit()
                return [TextContent(type="text", text=json.dumps({"log_id": str(log.id)}))]

            case _:
                return [TextContent(type="text", text=json.dumps({"error": f"Unknown tool: {name}"}))]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


if __name__ == "__main__":
    asyncio.run(main())
