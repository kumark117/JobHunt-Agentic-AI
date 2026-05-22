# JobHunt Agent

**Automated job hunt system with Agentic MCP architecture and Human-in-the-Loop control.**

Built for Kumar Krishnamoorthy — Senior Engineer in Bangalore targeting FullStack Architect / AI Engineer roles.

---

## What it does

1. **Discovers** jobs daily from LinkedIn, Naukri, Wellfound, Instahyre, HN Hiring, and hand-curated company careers pages
2. **Scores** each role for fit against Kumar's resume using Claude — only surfaces matches ≥ 65
3. **Tailors** resume bullets to each JD with a side-by-side diff view and a retry-on-rejection loop
4. **Drafts** a LinkedIn note and cover letter per role
5. **Pauses at 3 gates** so Kumar approves every consequential action — nothing is submitted automatically

---

## Architecture

```
Next.js Dashboard  ←  SSE push
       ↕ REST
FastAPI Backend (asyncio)
       ↕ stdio / JSON-RPC
5 MCP Servers: Discovery · Scoring · Tailor · Outreach · State
       ↕
PostgreSQL (persistent state machine)
```

**Pattern:** Same as the AI Researcher for Trading project — stdio MCP subprocess per request, asyncio Future-based HITL gates, SSE fan-out broadcast.

---

## Stack

| Layer | Tech |
|---|---|
| Frontend | Next.js 14 (App Router), TypeScript, Tailwind CSS |
| Backend | FastAPI (Python 3.11+), asyncio |
| AI | Anthropic Claude SDK — `claude-sonnet-4-20250514` |
| MCP | `mcp` Python SDK, stdio transport |
| Database | PostgreSQL 15, SQLAlchemy 2 (async), Alembic |
| Real-time | SSE (AsyncGenerator), asyncio.Queue fan-out |
| Dev | Docker Compose, VS Code |
| Deploy | Render (2 web services) |

---

## Quick start

### Prerequisites
- Docker & Docker Compose
- Python 3.11+
- Node 20+

### 1. Clone & configure

```bash
cp .env.example backend/.env
# Edit backend/.env — set ANTHROPIC_API_KEY at minimum
```

### 2. Start with Docker Compose

```bash
docker compose up
```

Dashboard: http://localhost:3000  
API docs: http://localhost:8000/docs

### 3. Run migrations manually (first time, without Docker)

```bash
cd backend
pip install -r requirements.txt
alembic upgrade head
uvicorn main:app --reload
```

```bash
cd frontend
npm install
npm run dev
```

---

## Human-in-the-Loop Gates

| Gate | Trigger | Your options |
|---|---|---|
| **Gate 1** Triage | fit score ≥ 65 surfaced | Approve / Skip / Adjust tailor toggle |
| **Gate 2** Resume | tailored diff ready | Approve / Reject+note (retry×3) / Manual override |
| **Gate 3** Apply | outreach drafts ready | Approve (mark Ready to Apply) / Edit / Skip |

Gate 2 feedback loop: your rejection note (e.g. _"Too generic — emphasise MCP experience more"_) is injected into the next tailor prompt. Max 3 retries before manual override mode.

---

## Resume tailoring — 3 control levels

| Level | Where | Effect |
|---|---|---|
| Global default | Settings panel | `always_tailor` / `never_tailor` / `ask_each_time` |
| Per-job toggle | Gate 1 card | Overrides global for this job only |
| HITL question | Gate 1 card (ask mode) | Explicit yes/no per job |

`tailor_skipped` is a first-class state — jobs on this path skip Gate 2 entirely and flow directly from Gate 1 → outreach → Gate 3.

---

## Project structure

```
├── backend/
│   ├── main.py                     # FastAPI app + lifespan
│   ├── pipeline_coordinator.py     # Full pipeline orchestrator
│   ├── hitl_gate.py                # asyncio.Future-based HITL
│   ├── sse_broadcaster.py          # asyncio.Queue fan-out
│   ├── settings_loader.py          # DB > config.json precedence
│   ├── config.json                 # Local dev settings
│   ├── mcp_servers/
│   │   ├── state_mcp_server.py     # M1 — pipeline state CRUD
│   │   ├── discovery_mcp_server.py # M2 — job aggregation
│   │   ├── scoring_mcp_server.py   # M3 — Claude fit scoring
│   │   ├── tailor_mcp_server.py    # M5 — Claude resume tailoring
│   │   └── outreach_mcp_server.py  # M6 — Claude outreach drafts
│   ├── mcp_clients/                # FastAPI-side wrappers
│   ├── routers/                    # jobs · pipeline · settings
│   ├── db/                         # SQLAlchemy models + session
│   ├── alembic/                    # Migrations
│   └── resume/kumar_resume.json    # JSON source of truth
│
├── frontend/
│   ├── app/
│   │   ├── page.tsx                # Dashboard — job queue
│   │   ├── jobs/[id]/page.tsx      # Job detail — score/diff/outreach
│   │   └── settings/page.tsx       # Settings panel
│   ├── components/
│   │   ├── JobCard.tsx             # Gate 1 triage card
│   │   ├── ResumeDiff.tsx          # Gate 2 side-by-side diff
│   │   ├── OutreachPanel.tsx       # Gate 3 outreach review
│   │   ├── SSEListener.tsx         # EventSource hook
│   │   ├── PipelineStatus.tsx      # State machine visualiser
│   │   └── TailorToggle.tsx        # Per-job tailor/original toggle
│   └── lib/
│       ├── api.ts                  # All API calls
│       └── types.ts                # Shared TypeScript types
│
├── docker-compose.yml
└── .env.example
```

---

## Build milestones

| Milestone | Focus | Status |
|---|---|---|
| M0 | Docker, schema, FastAPI skeleton, resume.json | ✅ Scaffolded |
| M1 | `state_mcp_server.py` — CRUD on jobs table | ✅ Done |
| M2 | `discovery_mcp_server.py` — LinkedIn, Naukri, Wellfound | ✅ Done |
| M3 | `scoring_mcp_server.py` + SSE broadcaster | ✅ Done |
| M4 | `hitl_gate.py` asyncio Future + /hitl endpoint | ✅ Done |
| M5 | `tailor_mcp_server.py` + Gate 2 retry loop | ✅ Done |
| M6 | `outreach_mcp_server.py` + pipeline_coordinator | ✅ Done |
| M7 | Next.js dashboard — all pages + components | ✅ Done |
| M8 | Render deploy + cron + PDF export + E2E tests + auth + rate limiting | ✅ Done |

---

## Environment variables

```env
DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/jobhunt
ANTHROPIC_API_KEY=sk-ant-...

# Discovery APIs (optional — sources without keys return empty lists)
RAPIDAPI_KEY=...        # LinkedIn Jobs via RapidAPI
NAUKRI_API_KEY=...      # Naukri REST API  
WELLFOUND_API_KEY=...   # Wellfound (AngelList) API

FIT_SCORE_THRESHOLD=65
MAX_TAILOR_RETRIES=3
```

---

## Why asyncio Future for HITL?

Polling the DB every N seconds for a human decision wastes CPU and introduces latency. The asyncio Future pattern suspends the coroutine at the gate with **zero resource cost** — the event loop is free. When you click Approve, the POST to `/hitl` resolves the future and the pipeline resumes **immediately**.

## Why stdio MCP?

Stateless, crash-isolated, independently testable. Any MCP-compatible host (Claude Desktop, Claude Code) can connect to the same servers without code changes.

---

Kumar Krishnamoorthy · kumar.softindies@gmail.com
# JobHunt-Agentic-AI
