# M0–M8 Generation Overview

**Project:** JobHunt Agentic AI  
**Spec version:** v1.1  
**Generated:** 2026-05-22  
**Architecture pattern:** Agentic MCP + HITL — mirrors AI Researcher for Trading project

---

## What was generated (M0–M7)

### M0 — Foundation (0.5 day estimate)

**Files created:**
- `docker-compose.yml` — Postgres + FastAPI + Next.js services with health checks
- `backend/Dockerfile` — Python 3.11-slim, installs deps, uvicorn entrypoint
- `frontend/Dockerfile` — Multi-stage Node 20 build with standalone output
- `backend/requirements.txt` — fastapi, uvicorn, sqlalchemy, alembic, asyncpg, anthropic, mcp, httpx, bs4, feedparser
- `backend/config.json` — Local dev settings (tailor_mode, thresholds, sources, target_roles)
- `backend/db/models.py` — SQLAlchemy 2 async models: `Job`, `HitlDecision`, `ResumeArtifact`, `OutreachArtifact`, `AgentLog`, `Setting`
- `backend/db/session.py` — `create_async_engine` + `async_sessionmaker`, `get_db` dependency
- `backend/alembic.ini` — Alembic config pointing to asyncpg URL
- `backend/alembic/env.py` — Async migration runner
- `backend/alembic/script.py.mako` — Migration template
- `backend/alembic/versions/001_initial_schema.py` — Full schema DDL + seed settings rows
- `backend/resume/kumar_resume.json` — Structured JSON resume (source of truth for all tailoring)
- `backend/main.py` — FastAPI app skeleton with lifespan, CORS, router registration
- `.env.example`, `.gitignore`

**Key decisions:**
- `resume/kumar_resume.json` is structured as `{skills, experience[{bullets[]}], projects[{bullets[]}]}` so the Tailor agent can surgically modify individual bullets
- Alembic uses asyncpg natively — no sync fallback needed
- Settings table seeded in migration 001 so `get_setting()` works before any UI interaction

---

### M1 — State MCP Server (1 day estimate)

**Files created:**
- `backend/mcp_servers/state_mcp_server.py` — 5 MCP tools: `get_pipeline_state`, `set_hitl_decision`, `list_pending_approvals`, `update_job_status`, `log_agent_step`
- `backend/mcp_clients/base_client.py` — `BaseMCPClient` wrapping `stdio_client` + `ClientSession`; per-request subprocess (intentional per spec §13.1)
- `backend/mcp_clients/state_client.py` — Typed wrapper with `state_client` singleton

**Key decisions:**
- Start with State MCP first — every subsequent agent needs a place to write; you can test the full MCP round-trip via Claude Desktop before touching FastAPI
- `list_pending_approvals` maps gate name → status set (`gate1` → `pending_triage, pending_triage_tailor`, etc.)
- Decision history is returned inline in `get_pipeline_state` so the dashboard can show full audit trail without a second request

---

### M2 — Discovery MCP Server (1.5 day estimate)

**Files created:**
- `backend/mcp_servers/discovery_mcp_server.py` — 4 tools: `search_jobs`, `fetch_jd_full`, `check_company_careers`, `parse_hn_thread`
- `backend/mcp_clients/discovery_client.py` — Typed wrapper + `discovery_client` singleton

**Key decisions:**
- Sources without API keys return empty lists gracefully — the server never crashes on missing credentials
- `fetch_jd_full` strips nav/footer/scripts via BeautifulSoup and returns `seniority_hint` + `remote_flag` to help scoring
- `check_company_careers` uses heuristic link-text matching against `TARGET_KEYWORDS` — good enough for P3 hand-curated targets
- `parse_hn_thread` uses HN Algolia API to find the monthly thread, then fetches top-100 comments

---

### M3 — Scoring MCP Server + SSE (1 day estimate)

**Files created:**
- `backend/mcp_servers/scoring_mcp_server.py` — 4 tools: `score_fit`, `explain_score`, `filter_batch`, `suggest_keywords`
- `backend/mcp_clients/scoring_client.py`
- `backend/sse_broadcaster.py` — `asyncio.Queue` fan-out; `subscribe()` / `unsubscribe()` / `broadcast()` / `stream()`

**Key decisions:**
- `score_fit` uses a structured prompt that returns `{score, matched, gaps, red_flags, summary, ats_keywords}` — all fields needed by Gate 1 card and job detail page
- SSE broadcaster uses per-subscriber `asyncio.Queue(maxsize=100)` — slow clients don't block the broadcast path; dead queues are pruned on `QueueFull`
- Keep-alive `: keep-alive\n\n` pings every 30s prevent proxy timeouts
- `filter_batch` is stateless — caller passes pre-scored `[{job_id, score}]` and gets back passing IDs; no DB needed

---

### M4 — HITL Gate (1 day estimate)

**Files created:**
- `backend/hitl_gate.py` — `HITLGate` class with `wait_for_decision()` / `resolve()` / `cancel()` / `list_pending()`; `Decision` dataclass
- `backend/routers/jobs.py` — CRUD: list/get/create jobs, resume artifacts, outreach artifacts, agent logs, tailor_override PATCH
- `backend/routers/pipeline.py` — `POST /run/{job_id}`, `POST /hitl/{gate}/{job_id}`, `GET /pending-gates`, `GET /sse`

**Key decisions:**
- `asyncio.Future` not `asyncio.Event` — futures carry the Decision payload directly, no separate state lookup after wake
- `resolve()` returns `bool` — FastAPI can 404 if no gate is pending for that job, catching stale or duplicate submissions
- `GET /sse` uses `StreamingResponse` with `AsyncGenerator` — compatible with Next.js `EventSource` and proxy buffering disabled via `X-Accel-Buffering: no`

---

### M5 — Tailor MCP Server + Pipeline Coordinator (2 day estimate)

**Files created:**
- `backend/mcp_servers/tailor_mcp_server.py` — 4 tools: `tailor_resume`, `diff_resume`, `retry_tailor`, `export_resume_pdf` (stub)
- `backend/mcp_clients/tailor_client.py`
- `backend/pipeline_coordinator.py` — Full `run_pipeline_for_job()` coroutine with Gate 1 → tailor/skip → Gate 2 retry loop → Gate 3

**Key decisions:**
- `tailor_resume` prompt explicitly forbids fabrication: "Do NOT add skills that aren't in the original resume"
- `retry_tailor` prepends `[Attempt N]` prefix so Claude can track improvement across retries
- `diff_resume` computes `changed_bullets` from the tailored output — no string diff needed since Claude returns structured change objects with `reason` fields
- `_resolve_tailor()` is a pure function returning `bool | None` — `None` means "ask" which the coordinator handles with a second HITL wait
- Pipeline writes `ResumeArtifact` inline (not via MCP) to avoid a round-trip subprocess call for DB writes the coordinator already owns

---

### M6 — Outreach MCP Server + Settings (1 day estimate)

**Files created:**
- `backend/mcp_servers/outreach_mcp_server.py` — 3 tools: `draft_linkedin_note`, `draft_cover_letter`, `personalise_outreach`
- `backend/mcp_clients/outreach_client.py` — includes `draft_all()` that fires note + letter in parallel
- `backend/settings_loader.py` — `get_setting()` / `set_setting()` / `get_all_settings()` with DB > config.json precedence
- `backend/routers/settings.py` — `GET /` returns merged settings, `POST /` persists to DB

**Key decisions:**
- LinkedIn note prompt enforces 300-char limit and "no generic phrases" rule — critical because LLMs default to enthusiasm-fluff
- `draft_all()` uses `asyncio.gather` — note and letter generated in parallel, halving latency
- Settings DB > config.json: DB values take precedence so changes from the UI hot-reload without restart; config.json is the fallback for local dev without a running DB

---

### M7 — Next.js Dashboard (2 day estimate)

**Files created:**
- `frontend/lib/types.ts` — All shared TypeScript types: `Job`, `FitSummary`, `DiffResult`, `ResumeArtifact`, `OutreachArtifact`, `SSEEvent`, `DecisionPayload`, `Settings`
- `frontend/lib/api.ts` — All API calls typed against those types; `createSSEConnection()` returns `EventSource`
- `frontend/app/layout.tsx` — Root layout with nav
- `frontend/app/globals.css` — Tailwind base
- `frontend/app/page.tsx` — Dashboard: job queue + SSE listener + status filter tabs
- `frontend/app/jobs/[id]/page.tsx` — Job detail: fit analysis, resume diff (Gate 2), outreach panel (Gate 3), JD text
- `frontend/app/settings/page.tsx` — Settings panel: tailor mode radio, thresholds, discovery source toggles
- `frontend/app/api/hitl/route.ts` — Next.js route handler proxying to FastAPI HITL endpoint
- `frontend/components/JobCard.tsx` — Gate 1 triage card with score badge, status, tailor toggle, approve/skip buttons
- `frontend/components/ResumeDiff.tsx` — Side-by-side diff with rejection note textarea and retry/approve/skip
- `frontend/components/OutreachPanel.tsx` — LinkedIn note + cover letter review with Gate 3 approve/skip
- `frontend/components/SSEListener.tsx` — `useEffect` EventSource hook that calls `onEvent` callback
- `frontend/components/PipelineStatus.tsx` — Dot-and-line state machine visualiser
- `frontend/components/TailorToggle.tsx` — Per-job Tailor / Use original segmented control

**Key decisions:**
- All interactive components are `"use client"` — server components handle data fetching in pages
- `SSEListener` is a headless component (returns null) — clean separation of event subscription from UI
- `ResumeDiff` renders `diff_json.changes[]` from the Tailor server directly — no client-side diffing needed
- Dashboard reloads job list on every SSE event that implies a status change — simple and correct

---

## M8 — Polish & Deploy (1 day)

**Files created/modified:**
- `render.yaml` — 3 Render services: `jobhunt-backend` (web), `jobhunt-frontend` (web), `jobhunt-discovery` (cron @ 02:00 UTC = 07:30 IST); free-tier Postgres DB; `API_SECRET` auto-generated
- `backend/cron_scheduler.py` — APScheduler `AsyncIOScheduler` running `run_discovery_and_queue()` on the IST cron; registered in FastAPI lifespan (`ENABLE_CRON=true`)
- `backend/cron_runner.py` — Standalone entry point for Render cron service: `python cron_runner.py`
- `backend/middleware/auth.py` — `APIKeyMiddleware` checking `X-API-Key` header; no-ops when `API_SECRET` unset (local dev); exempt paths: `/health`, `/docs`, `/openapi.json`, `/redoc`
- `backend/middleware/rate_limiter.py` — In-process 30-second cooldown per job_id; returns `(allowed, retry_after_seconds)`; wired to `POST /api/pipeline/run/{job_id}` with HTTP 429
- `backend/resume/pdf_exporter.py` — `_build_html()` renders tailored resume JSON to clean HTML; `export_pdf()` calls WeasyPrint via `asyncio.to_thread`; falls back to `.html` file when WeasyPrint not installed (local dev without system libs)
- `backend/Dockerfile` — Added WeasyPrint system deps: libpango, libpangocairo, libgdk-pixbuf2.0, shared-mime-info, fonts-liberation
- `backend/requirements.txt` — Added: apscheduler, weasyprint, pytest, pytest-asyncio, anyio[trio], aiosqlite, httpx
- `backend/main.py` — Added: APScheduler start/stop in lifespan, `APIKeyMiddleware`, structured logging
- `backend/routers/pipeline.py` — Rate limiter check on `POST /run/{job_id}`; HTTP 429 with `Retry-After` detail
- `backend/mcp_servers/tailor_mcp_server.py` — `export_resume_pdf` tool now calls `pdf_exporter.export_pdf()` via `asyncio.to_thread`
- `backend/pytest.ini` — `asyncio_mode = auto`, `testpaths = tests`
- `backend/tests/conftest.py` — SQLite in-memory test DB; `AsyncClient` with `ASGITransport`; `override_get_db` fixture; sample_resume, sample_jd, mock fixtures
- `backend/tests/test_pipeline_e2e.py` — 4 E2E tests covering: all-approved flow, Gate 1 skip → archived, Gate 2 reject+retry → applied, tailor_skipped path. Claude calls mocked with `AsyncMock`.
- `backend/tests/test_state_mcp.py` — 5 integration tests for jobs CRUD via HTTP API
- `backend/tests/test_pdf_export.py` — 5 unit tests for PDF exporter (HTML generation + WeasyPrint fallback)

**Key decisions:**

**Render cron vs APScheduler:** Both are implemented. APScheduler runs inside the FastAPI process (no extra service needed); Render cron calls `cron_runner.py` as a separate service — better for production since it doesn't tie up the web process. Use `ENABLE_CRON=false` on the backend web service and let the Render cron service handle discovery.

**WeasyPrint fallback:** Writes `.html` instead of `.pdf` when WeasyPrint system libs aren't available. This means `export_resume_pdf` never crashes locally — developers can inspect the HTML output without installing pango/cairo.

**Auth design:** Single shared secret in `X-API-Key` header. Render auto-generates the value (`generateValue: true`) and injects it into the frontend as an env var (not implemented yet — left as M8+ task since the dashboard is single-user anyway). The middleware no-ops when `API_SECRET=""` so local dev needs zero config.

**E2E test approach:** Pipeline runs as a real asyncio coroutine; HITL gates are resolved via `hitl_gate.resolve()` directly (not HTTP) so tests don't depend on request timing. Claude calls are mocked. SQLite via `aiosqlite` provides a fresh DB per test session with no Postgres dependency.

---

## File count summary

| Area | Files |
|---|---|
| Root config | 4 (.env.example, .gitignore, docker-compose.yml, README.md) |
| Backend foundation (M0) | 12 |
| MCP servers (M1–M6) | 5 |
| MCP clients (M1–M6) | 6 |
| Backend routers | 3 |
| Backend support | 4 (hitl_gate, sse_broadcaster, settings_loader, pipeline_coordinator) |
| Frontend config | 6 (package.json, tsconfig, tailwind, postcss, next.config, Dockerfile) |
| Frontend app | 5 (layout, globals, page, jobs/[id]/page, settings/page, api/hitl) |
| Frontend components | 6 |
| Frontend lib | 2 (api.ts, types.ts) |
| Docs | 2 (README.md, this file) |
| **Total** | **~58 files** |

---

## Test the MCP round-trip (before M8)

```bash
# 1. Start postgres
docker compose up postgres -d

# 2. Run migrations
cd backend && alembic upgrade head

# 3. Test state MCP server directly
echo '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}' | python mcp_servers/state_mcp_server.py

# 4. Or connect via Claude Desktop by adding to claude_desktop_config.json:
# {
#   "mcpServers": {
#     "jobhunt-state": {
#       "command": "python",
#       "args": ["/path/to/backend/mcp_servers/state_mcp_server.py"]
#     }
#   }
# }
```
