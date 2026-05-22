"""
M2 — Discovery MCP Server
Aggregates job listings from LinkedIn, Naukri, Wellfound, HN Hiring, and company careers pages.
Real API keys are loaded from env; sources without keys return empty lists gracefully.
"""
import asyncio
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from urllib.parse import quote_plus

import httpx
import feedparser
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

load_dotenv()

server = Server("discovery-server")

RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY", "")
WELLFOUND_API_KEY = os.getenv("WELLFOUND_API_KEY", "")
MOCK_DISCOVERY = os.getenv("MOCK_DISCOVERY", "false").strip().lower() == "true"

MOCK_JOBS = [
    {
        "source": "mock",
        "url": "https://mock.jobs/fullstack-architect-fintech-1",
        "title": "Full Stack Architect",
        "company": "FinEdge Technologies",
        "snippet": "We are looking for a Full Stack Architect with 8+ years of experience to lead our platform modernisation. Strong Node.js, React, AWS, and system design skills required. Remote-friendly, Bangalore base preferred.",
        "location": "Bangalore",
    },
    {
        "source": "mock",
        "url": "https://mock.jobs/ai-engineer-saas-2",
        "title": "AI Engineer",
        "company": "Clairo AI",
        "snippet": "Join our applied AI team to build production LLM pipelines. Experience with LangChain/LlamaIndex, RAG, vector DBs, and Claude or GPT APIs. Python, FastAPI, and MLOps background required. Remote.",
        "location": "Remote",
    },
    {
        "source": "mock",
        "url": "https://mock.jobs/principal-engineer-platform-3",
        "title": "Principal Engineer – Platform",
        "company": "Groww",
        "snippet": "Principal Engineer to own platform reliability and architecture across our microservices. Distributed systems, Kafka, Kubernetes, and strong mentorship skills required. Bangalore office.",
        "location": "Bangalore",
    },
    {
        "source": "mock",
        "url": "https://mock.jobs/senior-ai-engineer-healthtech-4",
        "title": "Senior AI Engineer",
        "company": "HealthPilot",
        "snippet": "Build AI-assisted clinical decision support tools. Python, Claude API, FHIR, and strong ML fundamentals required. Early stage startup, equity heavy, remote.",
        "location": "Remote",
    },
    {
        "source": "mock",
        "url": "https://mock.jobs/lead-fullstack-infra-5",
        "title": "Lead Full Stack Engineer",
        "company": "Razorpay",
        "snippet": "Lead full-stack engineer to drive our developer dashboard rebuild. React, TypeScript, Go services, Postgres. Strong ownership mindset. Bangalore hybrid.",
        "location": "Bangalore",
    },
]


# ── Tool definitions ────────────────────────────────────────────────────────

@server.list_tools()
async def list_tools():
    return [
        Tool(
            name="search_jobs",
            description="Search for jobs across configured platforms and return a list of listings",
            inputSchema={
                "type": "object",
                "properties": {
                    "keywords": {"type": "array", "items": {"type": "string"}},
                    "platforms": {"type": "array", "items": {"type": "string"}},
                    "location": {"type": "string"},
                    "days_back": {"type": "integer", "default": 7},
                },
                "required": ["keywords"],
            },
        ),
        Tool(
            name="fetch_jd_full",
            description="Fetch the full job description text from a URL",
            inputSchema={
                "type": "object",
                "properties": {"url": {"type": "string"}},
                "required": ["url"],
            },
        ),
        Tool(
            name="check_company_careers",
            description="Scrape a company careers page for open roles matching target keywords",
            inputSchema={
                "type": "object",
                "properties": {
                    "company_slug": {"type": "string"},
                    "careers_url": {"type": "string"},
                },
                "required": ["company_slug", "careers_url"],
            },
        ),
        Tool(
            name="parse_hn_thread",
            description="Parse the HackerNews Who's Hiring monthly thread for job listings",
            inputSchema={
                "type": "object",
                "properties": {
                    "month": {"type": "string"},
                    "year": {"type": "string"},
                },
                "required": ["month", "year"],
            },
        ),
    ]


# ── Handlers ────────────────────────────────────────────────────────────────

async def _search_linkedin(keywords: list[str], location: str, days_back: int) -> list[dict]:
    if not RAPIDAPI_KEY:
        return []
    query = " ".join(keywords)
    url = "https://linkedin-jobs-search.p.rapidapi.com/"
    headers = {
        "X-RapidAPI-Key": RAPIDAPI_KEY,
        "X-RapidAPI-Host": "linkedin-jobs-search.p.rapidapi.com",
        "Content-Type": "application/json",
    }
    payload = {
        "search_terms": query,
        "location": location or "Bangalore",
        "page": "1",
    }
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
            jobs = []
            for item in data[:20]:
                jobs.append({
                    "source": "linkedin",
                    "url": item.get("job_url", ""),
                    "title": item.get("job_title", ""),
                    "company": item.get("company_name", ""),
                    "snippet": item.get("job_description", "")[:300],
                    "location": item.get("job_location", ""),
                })
            return jobs
    except Exception as e:
        return [{"source": "linkedin", "error": str(e)}]


async def _search_naukri(keywords: list[str], location: str) -> list[dict]:
    query = quote_plus(" ".join(keywords))
    loc = quote_plus(location or "Bangalore")
    url = f"https://www.naukri.com/jobapi/v3/search?noOfResults=20&urlType=search_by_keyword&searchType=adv&keyword={query}&location={loc}&pageNo=1"
    headers = {
        "appid": "109",
        "systemid": "Naukri",
        "User-Agent": "Mozilla/5.0",
    }
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            jobs = []
            for item in data.get("jobDetails", []):
                jobs.append({
                    "source": "naukri",
                    "url": item.get("jdURL", ""),
                    "title": item.get("title", ""),
                    "company": item.get("companyName", ""),
                    "snippet": item.get("jobDescription", "")[:300],
                    "location": location,
                })
            return jobs
    except Exception as e:
        return [{"source": "naukri", "error": str(e)}]


async def _search_wellfound(keywords: list[str]) -> list[dict]:
    if not WELLFOUND_API_KEY:
        return []
    query = " ".join(keywords)
    url = f"https://api.wellfound.com/graphql"
    headers = {
        "Authorization": f"Bearer {WELLFOUND_API_KEY}",
        "Content-Type": "application/json",
    }
    gql = {
        "query": """
        query SearchJobs($query: String!) {
          jobListings(query: $query, first: 20) {
            nodes {
              id title slug
              startupRole { startup { name websiteUrl } }
              description
            }
          }
        }
        """,
        "variables": {"query": query},
    }
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(url, headers=headers, json=gql)
            resp.raise_for_status()
            nodes = resp.json().get("data", {}).get("jobListings", {}).get("nodes", [])
            return [
                {
                    "source": "wellfound",
                    "url": f"https://wellfound.com/jobs/{n.get('slug', '')}",
                    "title": n.get("title", ""),
                    "company": n.get("startupRole", {}).get("startup", {}).get("name", ""),
                    "snippet": (n.get("description") or "")[:300],
                    "location": "Remote/Flexible",
                }
                for n in nodes
            ]
    except Exception as e:
        return [{"source": "wellfound", "error": str(e)}]


async def _search_hn_rss(keywords: list[str]) -> list[dict]:
    now = datetime.now(timezone.utc)
    month = now.strftime("%B")
    year = now.strftime("%Y")
    all_listings = await _handle_parse_hn_thread(month, year)
    kw_lower = [k.lower() for k in keywords]
    matched = []
    for job in all_listings:
        text = (job.get("title", "") + " " + job.get("snippet", "")).lower()
        if any(kw in text for kw in kw_lower):
            matched.append(job)
    return matched


async def _handle_search_jobs(arguments: dict) -> list[dict]:
    if MOCK_DISCOVERY:
        return MOCK_JOBS

    keywords = arguments.get("keywords", [])
    platforms = arguments.get("platforms", ["linkedin", "naukri", "wellfound", "hn_hiring"])
    location = arguments.get("location", "Bangalore")
    days_back = arguments.get("days_back", 7)

    tasks = []
    if "linkedin" in platforms:
        tasks.append(_search_linkedin(keywords, location, days_back))
    if "naukri" in platforms:
        tasks.append(_search_naukri(keywords, location))
    if "wellfound" in platforms:
        tasks.append(_search_wellfound(keywords))
    if "hn_hiring" in platforms:
        tasks.append(_search_hn_rss(keywords))

    results = await asyncio.gather(*tasks, return_exceptions=True)
    all_jobs = []
    for r in results:
        if isinstance(r, list):
            all_jobs.extend(j for j in r if j.get("url"))  # drop error-only entries
    return all_jobs


async def _handle_fetch_jd(url: str) -> dict:
    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            resp = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")
            for tag in soup(["script", "style", "nav", "footer", "header"]):
                tag.decompose()
            text = soup.get_text(separator="\n", strip=True)
            seniority = "senior" if any(w in text.lower() for w in ["senior", "lead", "architect", "principal"]) else "mid"
            remote = any(w in text.lower() for w in ["remote", "wfh", "work from home"])
            return {
                "url": url,
                "jd_text": text[:8000],
                "seniority_hint": seniority,
                "remote_flag": remote,
            }
    except Exception as e:
        return {"url": url, "error": str(e)}


async def _handle_check_careers(company_slug: str, careers_url: str) -> list[dict]:
    TARGET_KEYWORDS = ["fullstack", "full stack", "architect", "ai engineer", "applied ai", "frontend", "platform engineer"]
    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            resp = await client.get(careers_url, headers={"User-Agent": "Mozilla/5.0"})
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")
            roles = []
            for a in soup.find_all("a", href=True):
                text = a.get_text(strip=True).lower()
                if any(kw in text for kw in TARGET_KEYWORDS):
                    href = a["href"]
                    if not href.startswith("http"):
                        from urllib.parse import urljoin
                        href = urljoin(careers_url, href)
                    roles.append({
                        "source": "company_careers",
                        "url": href,
                        "title": a.get_text(strip=True),
                        "company": company_slug,
                        "snippet": "",
                        "location": "Bangalore/Remote",
                    })
            return roles[:10]
    except Exception as e:
        return [{"source": "company_careers", "company": company_slug, "error": str(e)}]


async def _handle_parse_hn_thread(month: str, year: str) -> list[dict]:
    query = f"who is hiring {month} {year}"
    search_url = f"https://hn.algolia.com/api/v1/search?query={quote_plus(query)}&tags=story"
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(search_url)
            resp.raise_for_status()
            hits = resp.json().get("hits", [])
            if not hits:
                return []
            thread_id = hits[0]["objectID"]
            comments_url = f"https://hn.algolia.com/api/v1/search?tags=comment,story_{thread_id}&hitsPerPage=100"
            resp2 = await client.get(comments_url)
            resp2.raise_for_status()
            comments = resp2.json().get("hits", [])
            jobs = []
            for c in comments[:50]:
                text = BeautifulSoup(c.get("comment_text", ""), "html.parser").get_text()
                jobs.append({
                    "source": "hn_hiring",
                    "url": f"https://news.ycombinator.com/item?id={c.get('objectID')}",
                    "title": text[:80],
                    "company": "HN Submission",
                    "snippet": text[:300],
                    "location": "Various",
                })
            return jobs
    except Exception as e:
        return [{"source": "hn_hiring", "error": str(e)}]


@server.call_tool()
async def call_tool(name: str, arguments: dict):
    match name:
        case "search_jobs":
            jobs = await _handle_search_jobs(arguments)
            return [TextContent(type="text", text=json.dumps(jobs))]
        case "fetch_jd_full":
            result = await _handle_fetch_jd(arguments["url"])
            return [TextContent(type="text", text=json.dumps(result))]
        case "check_company_careers":
            roles = await _handle_check_careers(arguments["company_slug"], arguments["careers_url"])
            return [TextContent(type="text", text=json.dumps(roles))]
        case "parse_hn_thread":
            jobs = await _handle_parse_hn_thread(arguments["month"], arguments["year"])
            return [TextContent(type="text", text=json.dumps(jobs))]
        case _:
            return [TextContent(type="text", text=json.dumps({"error": f"Unknown tool: {name}"}))]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
