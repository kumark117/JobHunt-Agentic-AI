# JobHunt Agentic AI

An end-to-end agentic job-hunt system built for a senior engineer targeting **FullStack Architect / AI Engineer** roles in Bangalore. Discovers jobs daily, scores them for fit using Claude, tailors the resume, drafts outreach — and pauses at three explicit gates so a human approves every consequential action before anything is submitted.

---

## Demo flow

```
Run Discovery → 5 jobs scored → 3 pass threshold
   ↓ Gate 1 — Triage: Approve / Skip each job
   ↓ Claude tailors resume bullets to the JD
   ↓ Gate 2 — Resume review: Approve / Reject with note (retry loop up to 3×)
   ↓ Claude drafts LinkedIn note + cover letter
   ↓ Gate 3 — Apply: Fast Apply ⚡ or review drafts first
```

---

## Architecture

```
┌─────────────────────────────────┐
│  Next.js 14 Dashboard           │  localhost:3000
│  JobCard · ResumeDiff ·         │
│  OutreachPanel · SSEListener    │
└────────────┬────────────────────┘
             │ REST + SSE
┌────────────▼────────────────────┐
│  FastAPI (asyncio)              │  localhost:8000
│  pipeline_coordinator.py        │
│  hitl_gate.py (asyncio.Future)  │
│  sse_broadcaster.py             │
└────────────┬────────────────────┘
             │ stdio / JSON-RPC (MCP)
┌────────────▼────────────────────┐
│  5 MCP Servers (subprocesses)   │
│  State · Discovery · Scoring    │
│  Tailor · Outreach              │
└────────────┬────────────────────┘
             │
┌────────────▼────────────────────┐
│  PostgreSQL 15                  │
│  Jobs · HitlDecisions ·         │
│  ResumeArtifacts · AgentLogs    │
└─────────────────────────────────┘
```

**Key design choices:**

- **MCP stdio per request** — each tool call spawns a fresh subprocess. Crash-isolated, stateless, and any MCP-compatible host (Claude Desktop, Claude Code) can connect to the same servers without code changes.
- **`asyncio.Future` for HITL gates** — the pipeline coroutine suspends at a gate with zero CPU cost. Clicking Approve resolves the future and the coroutine resumes in microseconds, no polling.
- **SSE fan-out** — one `asyncio.Queue` per browser tab; the backend pushes events (`gate1_ready`, `gate2_ready`, `job_applied`, …) that refresh the dashboard without manual reloads.
- **Orphan recovery on startup** — any jobs stuck mid-pipeline when the server restarts are automatically detected and their pipeline coroutines restarted in the FastAPI lifespan.

---

## Stack

| Layer | Tech |
|---|---|
| Frontend | Next.js 14 (App Router), TypeScript, Tailwind CSS |
| Backend | FastAPI, Python 3.11, asyncio |
| AI | Anthropic Claude (`claude-sonnet-4-6`) via MCP |
| MCP | `mcp` Python SDK, stdio transport |
| Database | PostgreSQL 15, SQLAlchemy 2 async, Alembic |
| Real-time | Server-Sent Events, `asyncio.Queue` fan-out |
| Scheduling | APScheduler (in-process) + standalone `cron_runner.py` for Render |
| Deploy | Docker Compose (dev), Render (prod) |

---

## Quick start

**Prerequisites:** Docker Desktop, Node 20+

```bash
# 1. Configure environment
cp backend/.env.example backend/.env
# Set ANTHROPIC_API_KEY in backend/.env

# 2. Start everything
docker compose up

# Dashboard  →  http://localhost:3000
# API docs   →  http://localhost:8000/docs
```

**First run:** click **Run Discovery** in the dashboard. With `MOCK_DISCOVERY=true` (default), 5 realistic mock jobs are scored by Claude and surfaced for triage. Switch to real sources by setting your API keys and `MOCK_DISCOVERY=false`.

---

## Human-in-the-Loop gates

| Gate | Trigger | Options |
|---|---|---|
| **Gate 1 — Triage** | Fit score ≥ 65 surfaced | Approve · Skip · Set tailor mode per-job |
| **Gate 2 — Resume** | Tailored diff ready | Approve · Reject + note (reruns tailor) · Manual override |
| **Gate 3 — Apply** | Outreach drafts ready | Fast Apply ⚡ · Review drafts then Apply · Skip |

Gate 2 feedback loop: your rejection note (e.g. *"Too generic — emphasise MCP experience"*) is injected into the next tailor prompt. After 3 failures the job moves to manual override mode.

`tailor_skipped` is a first-class status — jobs on the "Use original" path skip Gate 2 entirely and flow directly from Gate 1 → outreach → Gate 3.

---

## Resume tailoring — 3 control levels

| Level | Where | Effect |
|---|---|---|
| Global default | Settings page | `always_tailor` / `never_tailor` / `ask_each_time` |
| Per-job toggle | Gate 1 card | Overrides global for this job only |
| HITL question | Gate 1 card (ask mode) | Explicit yes/no prompt per job |

---

## Project structure

```
├── backend/
│   ├── main.py                      # FastAPI app + lifespan (orphan recovery, cron)
│   ├── pipeline_coordinator.py      # Full pipeline orchestrator for one job
│   ├── hitl_gate.py                 # asyncio.Future-based HITL pause/resume
│   ├── sse_broadcaster.py           # asyncio.Queue fan-out to dashboard
│   ├── cron_scheduler.py            # Daily discovery → score → queue
│   ├── cron_runner.py               # Standalone entry for Render cron service
│   ├── settings_loader.py           # DB > config.json precedence
│   ├── mcp_servers/
│   │   ├── state_mcp_server.py      # M1 — pipeline state CRUD
│   │   ├── discovery_mcp_server.py  # M2 — LinkedIn, Naukri, Wellfound, HN, careers
│   │   ├── scoring_mcp_server.py    # M3 — Claude fit scoring (score, gaps, red flags)
│   │   ├── tailor_mcp_server.py     # M5 — Claude resume tailoring + diff
│   │   └── outreach_mcp_server.py   # M6 — Claude LinkedIn note + cover letter
│   ├── mcp_clients/                 # FastAPI-side typed wrappers
│   ├── routers/
│   │   ├── jobs.py                  # CRUD + reset endpoint
│   │   ├── pipeline.py              # run · hitl · discovery · SSE · debug
│   │   └── settings.py
│   ├── middleware/
│   │   ├── auth.py                  # X-API-Key header check (no-op in dev)
│   │   └── rate_limiter.py          # 30s cooldown per job_id
│   ├── db/
│   │   ├── models.py                # Job, HitlDecision, ResumeArtifact, OutreachArtifact, AgentLog, Setting
│   │   └── session.py
│   ├── alembic/versions/            # Schema migrations
│   ├── resume/kumar_resume.json     # JSON resume — source of truth for tailoring
│   └── tests/                       # E2E + integration + unit tests
│
├── frontend/
│   ├── app/
│   │   ├── page.tsx                 # Dashboard — job queue, filters, Run Discovery
│   │   ├── jobs/[id]/page.tsx       # Job detail — fit analysis, diff, outreach
│   │   └── settings/page.tsx        # Settings panel
│   ├── components/
│   │   ├── JobCard.tsx              # Gate 1 triage + Fast Apply (Gate 3)
│   │   ├── ResumeDiff.tsx           # Gate 2 side-by-side diff + retry
│   │   ├── OutreachPanel.tsx        # Gate 3 draft review + Apply
│   │   ├── SSEListener.tsx          # EventSource hook
│   │   ├── PipelineStatus.tsx       # Dot-and-line state machine visualiser
│   │   ├── TailorToggle.tsx         # Per-job tailor/original segmented control
│   │   └── VersionBadge.tsx         # FE + API version in nav
│   └── lib/
│       ├── api.ts                   # All typed API calls
│       └── types.ts                 # Shared TypeScript types
│
├── docker-compose.yml
└── render.yaml                      # Render deploy (2 web services + cron)
```

---

## Environment variables

```env
# Required
DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/jobhunt
ANTHROPIC_API_KEY=sk-ant-...
LLM_MODEL=claude-sonnet-4-6

# Discovery (optional — sources without keys return empty lists)
RAPIDAPI_KEY=...         # LinkedIn Jobs via RapidAPI
WELLFOUND_API_KEY=...    # Wellfound (AngelList) API

# Dev mode
MOCK_DISCOVERY=true      # Use built-in mock jobs instead of live APIs

# Runtime
FIT_SCORE_THRESHOLD=65
MAX_TAILOR_RETRIES=3
DISCOVERY_CRON=0 8 * * *
ENABLE_CRON=true
API_SECRET=              # Leave empty to disable auth locally
```

---

## Useful commands

```bash
# Trigger discovery manually (without the UI button)
docker compose exec backend python cron_runner.py

# Reset all pipeline data
curl -X DELETE http://localhost:8000/api/jobs/reset

# Check which HITL gates are currently awaiting decisions
curl http://localhost:8000/api/pipeline/pending-gates

# Debug discovery — see raw MCP response
curl http://localhost:8000/api/pipeline/debug-discovery

# Run backend tests
docker compose exec backend pytest
```

---

## Deploy to Render

`render.yaml` provisions:
- **`jobhunt-backend`** — FastAPI web service (`ENABLE_CRON=false`)
- **`jobhunt-frontend`** — Next.js web service
- **`jobhunt-discovery`** — Cron service running `python cron_runner.py` daily at 02:00 UTC (07:30 IST)
- **PostgreSQL** free-tier database

```bash
# Push to your Render-connected repo — render.yaml handles the rest
git push origin main
```

---

## Why asyncio.Future for HITL?

Polling a database every N seconds for a human decision wastes CPU and adds latency. The `asyncio.Future` pattern suspends the pipeline coroutine at the gate with **zero resource cost** — the event loop is fully free. When you click Approve, the `POST /hitl` endpoint resolves the future and the pipeline resumes **immediately**, with the Decision payload delivered directly to the waiting coroutine — no follow-up DB read needed.

## Why stdio MCP?

Per-request subprocess isolation means a crash in one MCP server (e.g. a malformed Claude response breaking JSON parsing) cannot corrupt the FastAPI process or other in-flight jobs. Each server is independently testable via stdin/stdout. And any MCP-compatible client — Claude Desktop, Claude Code, a future Claude agent — can call the same tools without any code changes on the server side.

---

Kumar Krishnamoorthy · [kumar.softindies@gmail.com](mailto:kumar.softindies@gmail.com)
