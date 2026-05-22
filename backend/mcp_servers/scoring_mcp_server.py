"""
M3 — Scoring MCP Server
Uses Claude to score job fit against Kumar's resume.
Returns structured FitScore with matched skills, gaps, and red flags.
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

server = Server("scoring-server")
claude = anthropic.AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
MODEL = os.getenv("LLM_MODEL", "claude-sonnet-4-6")

SCORE_SYSTEM = """You are an expert technical recruiter evaluating job fit for a senior software engineer.
You return ONLY valid JSON — no markdown, no explanation, just the JSON object."""

SCORE_PROMPT = """Evaluate the fit between this job description and candidate resume.

JOB DESCRIPTION:
{jd_text}

CANDIDATE RESUME (JSON):
{resume_json}

Return a JSON object with exactly these fields:
{{
  "score": <integer 0-100 representing overall fit>,
  "matched": [<list of specific skills/experiences that match>],
  "gaps": [<list of requirements the candidate lacks>],
  "red_flags": [<list of dealbreakers or concerns>],
  "summary": "<2 sentence summary of fit>",
  "ats_keywords": [<important ATS keywords present in JD>]
}}

Scoring guide:
- 85-100: Excellent fit, strong match on most requirements
- 70-84: Good fit, minor gaps
- 55-69: Moderate fit, some significant gaps
- 40-54: Weak fit, major gaps
- 0-39: Poor fit or disqualifying factors"""


@server.list_tools()
async def list_tools():
    return [
        Tool(
            name="score_fit",
            description="Score a job description against Kumar's resume using Claude",
            inputSchema={
                "type": "object",
                "properties": {
                    "jd_text": {"type": "string"},
                    "resume_json": {"type": "object"},
                },
                "required": ["jd_text", "resume_json"],
            },
        ),
        Tool(
            name="explain_score",
            description="Generate a human-readable explanation for a fit score",
            inputSchema={
                "type": "object",
                "properties": {
                    "fit_summary": {"type": "object"},
                    "job_title": {"type": "string"},
                    "company": {"type": "string"},
                },
                "required": ["fit_summary"],
            },
        ),
        Tool(
            name="filter_batch",
            description="Filter a list of job IDs by fit score threshold (requires pre-scored jobs)",
            inputSchema={
                "type": "object",
                "properties": {
                    "scores": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "job_id": {"type": "string"},
                                "score": {"type": "integer"},
                            },
                        },
                    },
                    "threshold": {"type": "integer", "default": 65},
                },
                "required": ["scores"],
            },
        ),
        Tool(
            name="suggest_keywords",
            description="Extract ATS keywords from a JD that are missing from the resume",
            inputSchema={
                "type": "object",
                "properties": {
                    "jd_text": {"type": "string"},
                    "resume_keywords": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["jd_text"],
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
        case "score_fit":
            jd_text = arguments["jd_text"][:6000]
            resume_str = json.dumps(arguments["resume_json"], indent=2)[:3000]
            prompt = SCORE_PROMPT.format(jd_text=jd_text, resume_json=resume_str)

            response = await claude.messages.create(
                model=MODEL,
                max_tokens=1024,
                system=SCORE_SYSTEM,
                messages=[{"role": "user", "content": prompt}],
            )
            result = _extract_json(response.content[0].text)
            return [TextContent(type="text", text=json.dumps(result))]

        case "explain_score":
            fit = arguments["fit_summary"]
            title = arguments.get("job_title", "this role")
            company = arguments.get("company", "this company")
            score = fit.get("score", "N/A")
            matched = ", ".join(fit.get("matched", [])[:5])
            gaps = ", ".join(fit.get("gaps", [])[:3])
            explanation = (
                f"**Fit Score: {score}/100** for {title} at {company}\n\n"
                f"**Why it matches:** {matched or 'No strong matches'}\n\n"
                f"**Key gaps:** {gaps or 'None identified'}\n\n"
                f"**Summary:** {fit.get('summary', '')}"
            )
            return [TextContent(type="text", text=json.dumps({"explanation": explanation}))]

        case "filter_batch":
            threshold = arguments.get("threshold", 65)
            passing = [
                s["job_id"]
                for s in arguments["scores"]
                if s.get("score", 0) >= threshold
            ]
            return [TextContent(type="text", text=json.dumps(passing))]

        case "suggest_keywords":
            jd_text = arguments["jd_text"][:4000]
            resume_kw = set(k.lower() for k in arguments.get("resume_keywords", []))

            response = await claude.messages.create(
                model=MODEL,
                max_tokens=512,
                system="Extract technical keywords and skills from job descriptions. Return JSON only.",
                messages=[
                    {
                        "role": "user",
                        "content": f"Extract all technical skills, tools, and keywords from this JD. Return as JSON: {{\"keywords\": [...]}}\n\nJD:\n{jd_text}",
                    }
                ],
            )
            result = _extract_json(response.content[0].text)
            all_kw = result.get("keywords", [])
            missing = [k for k in all_kw if k.lower() not in resume_kw]
            return [TextContent(type="text", text=json.dumps({"missing_keywords": missing}))]

        case _:
            return [TextContent(type="text", text=json.dumps({"error": f"Unknown tool: {name}"}))]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
