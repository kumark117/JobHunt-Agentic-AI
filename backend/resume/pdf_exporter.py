"""
WeasyPrint-based PDF export for tailored resumes.
Input: tailored_json (same structure as kumar_resume.json + tailored sections/summary)
Output: PDF bytes written to /app/exports/{job_id}.pdf
"""
import os
from pathlib import Path
from typing import Any

EXPORTS_DIR = Path("/app/exports")


def _build_html(resume: dict[str, Any]) -> str:
    name = resume.get("name", "Kumar Krishnamoorthy")
    email = resume.get("email", "")
    location = resume.get("location", "")
    title = resume.get("title", "")
    summary = resume.get("summary", "")
    skills = resume.get("skills", {})
    experience = resume.get("experience", resume.get("sections", []))
    projects = resume.get("projects", [])
    education = resume.get("education", {})
    certifications = resume.get("certifications", [])

    def skill_chips(items: list) -> str:
        return "".join(f'<span class="chip">{s}</span>' for s in items)

    def bullets_html(bullets: list) -> str:
        return "".join(f"<li>{b}</li>" for b in bullets)

    experience_html = ""
    for exp in experience:
        if not isinstance(exp, dict):
            continue
        experience_html += f"""
        <div class="entry">
          <div class="entry-header">
            <strong>{exp.get("title", "")}</strong> — {exp.get("company", "")}
            <span class="meta">{exp.get("location", "")} · {exp.get("period", "")}</span>
          </div>
          <ul>{bullets_html(exp.get("bullets", []))}</ul>
        </div>"""

    projects_html = ""
    for proj in projects:
        if not isinstance(proj, dict):
            continue
        tech_tags = " ".join(f'<span class="chip small">{t}</span>' for t in proj.get("tech", []))
        projects_html += f"""
        <div class="entry">
          <div class="entry-header">
            <strong>{proj.get("name", "")}</strong>
            <span class="meta">{tech_tags}</span>
          </div>
          <p class="proj-desc">{proj.get("description", "")}</p>
          <ul>{bullets_html(proj.get("bullets", []))}</ul>
        </div>"""

    skills_html = "".join(
        f'<div class="skill-row"><span class="skill-label">{k.replace("_", " ").title()}</span>'
        f'<div class="chips">{skill_chips(v if isinstance(v, list) else [v])}</div></div>'
        for k, v in skills.items()
    )

    cert_html = "".join(f"<li>{c}</li>" for c in certifications)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: 'Helvetica Neue', Arial, sans-serif; font-size: 10pt; color: #1e293b; padding: 32px 40px; }}
  h1 {{ font-size: 18pt; color: #0f172a; }}
  h2 {{ font-size: 11pt; color: #0369a1; text-transform: uppercase; letter-spacing: 0.05em;
        border-bottom: 1px solid #e2e8f0; margin: 16px 0 8px; padding-bottom: 3px; }}
  .header {{ margin-bottom: 12px; }}
  .contact {{ font-size: 9pt; color: #475569; margin-top: 3px; }}
  .role {{ font-size: 10pt; color: #475569; margin-top: 2px; }}
  .summary {{ font-size: 9.5pt; color: #334155; line-height: 1.5; margin-bottom: 4px; }}
  .entry {{ margin-bottom: 10px; }}
  .entry-header {{ display: flex; justify-content: space-between; align-items: baseline; }}
  .meta {{ font-size: 8.5pt; color: #64748b; }}
  .proj-desc {{ font-size: 9pt; color: #475569; margin: 2px 0 4px; }}
  ul {{ padding-left: 16px; }}
  li {{ font-size: 9pt; line-height: 1.45; color: #334155; margin-bottom: 2px; }}
  .chips {{ display: flex; flex-wrap: wrap; gap: 4px; margin-top: 4px; }}
  .chip {{ background: #e0f2fe; color: #0369a1; padding: 1px 7px; border-radius: 99px; font-size: 8pt; }}
  .chip.small {{ font-size: 7.5pt; padding: 1px 5px; }}
  .skill-row {{ display: flex; gap: 8px; margin-bottom: 5px; align-items: flex-start; }}
  .skill-label {{ font-size: 8.5pt; font-weight: 600; color: #475569; min-width: 90px; padding-top: 2px; }}
</style>
</head>
<body>
  <div class="header">
    <h1>{name}</h1>
    <div class="role">{title}</div>
    <div class="contact">{email} · {location}</div>
  </div>

  <h2>Summary</h2>
  <p class="summary">{summary}</p>

  <h2>Skills</h2>
  {skills_html}

  <h2>Experience</h2>
  {experience_html}

  <h2>Projects</h2>
  {projects_html}

  <h2>Education</h2>
  <p style="font-size:9.5pt">{education.get("degree", "")} — {education.get("institution", "")} · {education.get("year", "")}</p>

  {"<h2>Certifications</h2><ul>" + cert_html + "</ul>" if certifications else ""}
</body>
</html>"""


def export_pdf(resume: dict[str, Any], job_id: str) -> str:
    EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
    pdf_path = EXPORTS_DIR / f"{job_id}.pdf"
    html = _build_html(resume)
    try:
        from weasyprint import HTML
        HTML(string=html, base_url=None).write_pdf(str(pdf_path))
    except ImportError:
        # WeasyPrint not installed — write HTML as fallback for local dev
        html_path = pdf_path.with_suffix(".html")
        html_path.write_text(html, encoding="utf-8")
        return str(html_path)
    return str(pdf_path)
