"""
M6 — Outreach MCP Server
Drafts LinkedIn notes and cover letters using Claude.
Personalises drafts with company-specific context.
"""
import asyncio
import json
import os
import re

import anthropic
from dotenv import load_dotenv
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

load_dotenv()

server = Server("outreach-server")
claude = anthropic.AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
MODEL = os.getenv("LLM_MODEL", "claude-sonnet-4-6")

OUTREACH_SYSTEM = """You are an expert career coach writing outreach for a senior software engineer.
Write in a professional, direct tone. Avoid fluff. Be specific about value, not generic about enthusiasm.
Return ONLY valid JSON."""


@server.list_tools()
async def list_tools():
    return [
        Tool(
            name="draft_linkedin_note",
            description="Draft a LinkedIn connection or InMail note for a job application",
            inputSchema={
                "type": "object",
                "properties": {
                    "jd_text": {"type": "string"},
                    "company": {"type": "string"},
                    "hiring_mgr": {"type": "string"},
                    "resume_summary": {"type": "string"},
                },
                "required": ["jd_text", "company", "resume_summary"],
            },
        ),
        Tool(
            name="draft_cover_letter",
            description="Draft a cover letter tailored to the JD and tailored resume",
            inputSchema={
                "type": "object",
                "properties": {
                    "jd_text": {"type": "string"},
                    "tailored_resume_json": {"type": "object"},
                    "tone": {"type": "string", "enum": ["formal", "conversational"], "default": "conversational"},
                },
                "required": ["jd_text", "tailored_resume_json"],
            },
        ),
        Tool(
            name="personalise_outreach",
            description="Update outreach drafts with company-specific context and hooks",
            inputSchema={
                "type": "object",
                "properties": {
                    "linkedin_note": {"type": "string"},
                    "cover_letter": {"type": "string"},
                    "company_context": {"type": "string"},
                    "job_id": {"type": "string"},
                },
                "required": ["linkedin_note", "cover_letter", "company_context"],
            },
        ),
    ]


def _extract_json(text: str) -> dict:
    match = re.search(r"\{[\s\S]*\}", text)
    if match:
        return json.loads(match.group())
    return json.loads(text)


@server.call_tool()
async def call_tool(name: str, arguments: dict):
    match name:
        case "draft_linkedin_note":
            jd_snippet = arguments["jd_text"][:1500]
            company = arguments["company"]
            hiring_mgr = arguments.get("hiring_mgr", "Hiring Manager")
            summary = arguments["resume_summary"]

            prompt = f"""Write a LinkedIn connection request note for this job.

Role at {company}: {jd_snippet}

Candidate summary: {summary}

Address it to: {hiring_mgr}

Rules:
- Max 300 characters (LinkedIn limit)
- Mention one specific thing about the role or company
- Lead with value, not "I'm interested in..."
- No generic phrases like "excited about this opportunity"

Return JSON: {{"subject": "<optional subject>", "body": "<note text>", "char_count": <integer>}}"""

            response = await claude.messages.create(
                model=MODEL,
                max_tokens=256,
                system=OUTREACH_SYSTEM,
                messages=[{"role": "user", "content": prompt}],
            )
            result = _extract_json(response.content[0].text)
            return [TextContent(type="text", text=json.dumps(result))]

        case "draft_cover_letter":
            jd_text = arguments["jd_text"][:3000]
            resume = arguments["tailored_resume_json"]
            tone = arguments.get("tone", "conversational")

            bullets = []
            for exp in resume.get("sections", resume.get("experience", [])):
                if isinstance(exp, dict):
                    bullets.extend(exp.get("bullets", [])[:2])

            prompt = f"""Write a cover letter for this job application.

JOB DESCRIPTION:
{jd_text}

CANDIDATE'S RELEVANT EXPERIENCE (bullets):
{chr(10).join(f'• {b}' for b in bullets[:6])}

CANDIDATE SUMMARY:
{resume.get("summary", "")}

Requirements:
- Tone: {tone}
- Length: 250-350 words
- 3 paragraphs: hook / evidence / close
- Be specific about tech and impact — no vague claims
- Do NOT start with "I am writing to apply"

Return JSON: {{"subject": "<email subject line>", "body": "<full letter text>", "word_count": <integer>}}"""

            response = await claude.messages.create(
                model=MODEL,
                max_tokens=1024,
                system=OUTREACH_SYSTEM,
                messages=[{"role": "user", "content": prompt}],
            )
            result = _extract_json(response.content[0].text)
            return [TextContent(type="text", text=json.dumps(result))]

        case "personalise_outreach":
            context = arguments["company_context"]
            note = arguments["linkedin_note"]
            letter = arguments["cover_letter"]

            prompt = f"""Improve these outreach drafts by weaving in company-specific context.

COMPANY CONTEXT:
{context}

CURRENT LINKEDIN NOTE:
{note}

CURRENT COVER LETTER:
{letter}

Make one or two specific references to the company context in each.
Keep the LinkedIn note under 300 characters.

Return JSON:
{{
  "linkedin_note": "<updated note>",
  "cover_letter": "<updated letter>"
}}"""

            response = await claude.messages.create(
                model=MODEL,
                max_tokens=1024,
                system=OUTREACH_SYSTEM,
                messages=[{"role": "user", "content": prompt}],
            )
            result = _extract_json(response.content[0].text)
            return [TextContent(type="text", text=json.dumps(result))]

        case _:
            return [TextContent(type="text", text=json.dumps({"error": f"Unknown tool: {name}"}))]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
