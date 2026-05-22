"""
M5 — Tailor MCP Server
Uses Claude to surgically tailor resume bullets to a specific JD.
Supports feedback injection for retry loops (Gate 2).
"""
import asyncio
import json
import os
import re
import sys

import anthropic
from dotenv import load_dotenv
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

load_dotenv()

server = Server("tailor-server")
claude = anthropic.AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
MODEL = os.getenv("LLM_MODEL", "claude-sonnet-4-6")

TAILOR_SYSTEM = """You are an expert resume writer specializing in tailoring technical resumes.
You make surgical edits — reorder emphasis, strengthen relevant bullets, and surface matching keywords.
You NEVER fabricate experience. You NEVER remove entire sections. You return ONLY valid JSON."""

TAILOR_PROMPT = """Tailor the candidate's resume to better match this job description.

JOB DESCRIPTION:
{jd_text}

CURRENT RESUME (JSON):
{resume_json}

{feedback_section}

Rules:
1. Only modify the 'bullets' arrays in experience and projects sections
2. You may reorder bullets to put most relevant first
3. You may strengthen wording to better reflect JD language (same facts, better framing)
4. Do NOT add skills that aren't in the original resume
5. Do NOT remove any section or experience entry

Return JSON with exactly this structure:
{{
  "sections": [<same structure as input resume experience/projects>],
  "changed_bullets": [
    {{
      "section": "<company or project name>",
      "original": "<original bullet text>",
      "tailored": "<new bullet text>",
      "reason": "<why this change>"
    }}
  ],
  "summary": "<updated professional summary tailored to this role>"
}}"""


@server.list_tools()
async def list_tools():
    return [
        Tool(
            name="tailor_resume",
            description="Tailor resume bullets to a specific JD using Claude",
            inputSchema={
                "type": "object",
                "properties": {
                    "jd_text": {"type": "string"},
                    "resume_json": {"type": "object"},
                    "feedback": {"type": "string"},
                },
                "required": ["jd_text", "resume_json"],
            },
        ),
        Tool(
            name="diff_resume",
            description="Compute diff between original and tailored resume",
            inputSchema={
                "type": "object",
                "properties": {
                    "original_json": {"type": "object"},
                    "tailored_json": {"type": "object"},
                },
                "required": ["original_json", "tailored_json"],
            },
        ),
        Tool(
            name="retry_tailor",
            description="Re-tailor resume with Kumar's rejection feedback injected",
            inputSchema={
                "type": "object",
                "properties": {
                    "jd_text": {"type": "string"},
                    "resume_json": {"type": "object"},
                    "rejection_note": {"type": "string"},
                    "attempt_n": {"type": "integer"},
                },
                "required": ["jd_text", "resume_json", "rejection_note"],
            },
        ),
        Tool(
            name="export_resume_pdf",
            description="Stub: export tailored resume JSON to PDF path (returns path)",
            inputSchema={
                "type": "object",
                "properties": {
                    "tailored_json": {"type": "object"},
                    "job_id": {"type": "string"},
                },
                "required": ["tailored_json", "job_id"],
            },
        ),
    ]


def _extract_json(text: str) -> dict:
    match = re.search(r"\{[\s\S]*\}", text)
    if match:
        return json.loads(match.group())
    return json.loads(text)


async def _tailor(jd_text: str, resume_json: dict, feedback: str | None = None) -> dict:
    feedback_section = ""
    if feedback:
        feedback_section = f"\nKUMAR'S FEEDBACK ON PREVIOUS VERSION:\n{feedback}\nPlease address this feedback in the new version.\n"

    prompt = TAILOR_PROMPT.format(
        jd_text=jd_text[:5000],
        resume_json=json.dumps(resume_json, indent=2)[:3000],
        feedback_section=feedback_section,
    )

    response = await claude.messages.create(
        model=MODEL,
        max_tokens=2048,
        system=TAILOR_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )
    return _extract_json(response.content[0].text)


@server.call_tool()
async def call_tool(name: str, arguments: dict):
    match name:
        case "tailor_resume":
            result = await _tailor(
                arguments["jd_text"],
                arguments["resume_json"],
                arguments.get("feedback"),
            )
            return [TextContent(type="text", text=json.dumps(result))]

        case "diff_resume":
            original = arguments["original_json"]
            tailored = arguments["tailored_json"]

            changed = tailored.get("changed_bullets", [])
            added = [c["tailored"] for c in changed]
            removed = [c["original"] for c in changed]
            diff = {
                "added": added,
                "removed": removed,
                "reordered": [],
                "summary_changed": tailored.get("summary") != original.get("summary"),
                "change_count": len(changed),
                "changes": changed,
            }
            return [TextContent(type="text", text=json.dumps(diff))]

        case "retry_tailor":
            result = await _tailor(
                arguments["jd_text"],
                arguments["resume_json"],
                feedback=f"[Attempt {arguments.get('attempt_n', 2)}] {arguments['rejection_note']}",
            )
            return [TextContent(type="text", text=json.dumps(result))]

        case "export_resume_pdf":
            job_id = arguments["job_id"]
            tailored = arguments["tailored_json"]
            sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
            from resume.pdf_exporter import export_pdf
            try:
                pdf_path = await asyncio.to_thread(export_pdf, tailored, job_id)
                return [TextContent(type="text", text=json.dumps({"pdf_path": pdf_path, "status": "ok"}))]
            except Exception as e:
                return [TextContent(type="text", text=json.dumps({"error": str(e), "status": "failed"}))]

        case _:
            return [TextContent(type="text", text=json.dumps({"error": f"Unknown tool: {name}"}))]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
