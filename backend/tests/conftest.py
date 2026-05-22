"""
pytest fixtures for the JobHunt Agent backend.
Uses an in-memory SQLite DB for isolation (no Postgres needed for unit/integration tests).
E2E tests against real DB use --db-url flag or DATABASE_URL env.
"""
import asyncio
import json
import os
from pathlib import Path
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

# Point to SQLite for tests (no Postgres needed)
TEST_DB_URL = "sqlite+aiosqlite:///./test_jobhunt.db"

os.environ.setdefault("DATABASE_URL", TEST_DB_URL)
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")
os.environ.setdefault("API_SECRET", "")  # disable auth in tests

from db.models import Base
from db.session import get_db
from main import app


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session")
async def test_engine():
    engine = create_async_engine(TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def client(test_engine) -> AsyncGenerator[AsyncClient, None]:
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False)

    async def override_get_db():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


RESUME_PATH = Path(__file__).parent.parent / "resume" / "kumar_resume.json"


@pytest.fixture
def sample_resume() -> dict:
    with open(RESUME_PATH) as f:
        return json.load(f)


@pytest.fixture
def sample_jd() -> str:
    return """
    Senior FullStack Architect — AI Platform Team

    We are building an AI-native platform for financial services. You will architect
    the frontend and backend systems that power our agent orchestration layer.

    Requirements:
    - 10+ years software engineering, 5+ years architecture
    - React, Next.js, TypeScript — expert level
    - Python, FastAPI — strong proficiency
    - AI/ML systems: experience with LLMs, agent frameworks (LangChain, MCP, etc.)
    - PostgreSQL, Redis — production experience
    - Strong opinions on system design, API contracts, and observability

    Nice to have:
    - Experience with Claude / Anthropic API
    - Open-source contributions
    - Experience hiring and growing engineering teams

    Location: Bangalore (hybrid) or Remote
    """


@pytest.fixture
def mock_score_result() -> dict:
    return {
        "score": 88,
        "matched": ["React", "Next.js", "FastAPI", "PostgreSQL", "Claude SDK", "MCP"],
        "gaps": ["Financial services domain", "Team hiring experience"],
        "red_flags": [],
        "summary": "Strong technical fit — 8/10 requirements match directly. Domain gap is minor.",
        "ats_keywords": ["FullStack Architect", "AI Platform", "Next.js", "FastAPI", "MCP"],
    }


@pytest.fixture
def mock_tailor_result(sample_resume) -> dict:
    return {
        "sections": sample_resume.get("experience", []),
        "changed_bullets": [
            {
                "section": "Acme Fintech Pvt Ltd",
                "original": "Built a design system and component library",
                "tailored": "Architected a design system and component library for an AI-native platform",
                "reason": "Align with AI Platform framing in JD",
            }
        ],
        "summary": "FullStack Architect with 15+ years building AI-native systems. Expert in React, Next.js, FastAPI, and MCP agent orchestration.",
    }


@pytest.fixture
def mock_outreach_result() -> dict:
    return {
        "linkedin_note": {
            "body": "Hi — I architect React/FastAPI systems and have shipped an MCP agent platform. Your AI Platform role looks like a strong match. Would love to connect.",
            "char_count": 175,
        },
        "cover_letter": {
            "subject": "FullStack Architect — AI Platform Team",
            "body": "Dear Hiring Manager,\n\nI have spent the last 4 years...",
            "word_count": 280,
        },
    }
