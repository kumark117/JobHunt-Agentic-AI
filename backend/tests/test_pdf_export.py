"""
Unit tests for the PDF exporter — verifies HTML generation without WeasyPrint installed.
"""
import json
from pathlib import Path

import pytest

from resume.pdf_exporter import _build_html, export_pdf

RESUME_PATH = Path(__file__).parent.parent / "resume" / "kumar_resume.json"


@pytest.fixture
def resume():
    with open(RESUME_PATH) as f:
        return json.load(f)


def test_build_html_contains_name(resume):
    html = _build_html(resume)
    assert "Kumar Krishnamoorthy" in html


def test_build_html_contains_experience(resume):
    html = _build_html(resume)
    assert "Acme Fintech" in html


def test_build_html_contains_summary(resume):
    html = _build_html(resume)
    assert resume["summary"][:30] in html


def test_build_html_contains_skills(resume):
    html = _build_html(resume)
    assert "React" in html
    assert "FastAPI" in html


def test_export_pdf_fallback_writes_html(resume, tmp_path, monkeypatch):
    monkeypatch.setattr("resume.pdf_exporter.EXPORTS_DIR", tmp_path)

    # Force ImportError for WeasyPrint
    import builtins
    real_import = builtins.__import__

    def mock_import(name, *args, **kwargs):
        if name == "weasyprint":
            raise ImportError("WeasyPrint not installed")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", mock_import)

    job_id = "test-job-123"
    path = export_pdf(resume, job_id)
    assert path.endswith(".html")
    html_path = Path(path)
    assert html_path.exists()
    content = html_path.read_text()
    assert "Kumar Krishnamoorthy" in content
