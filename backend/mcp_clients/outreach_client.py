from mcp_clients.base_client import BaseMCPClient


class OutreachClient(BaseMCPClient):
    def __init__(self):
        super().__init__("outreach_mcp_server.py")

    async def draft_linkedin_note(
        self,
        jd_text: str,
        company: str,
        resume_summary: str,
        hiring_mgr: str | None = None,
    ) -> dict:
        args: dict = {"jd_text": jd_text, "company": company, "resume_summary": resume_summary}
        if hiring_mgr:
            args["hiring_mgr"] = hiring_mgr
        return await self.call_tool("draft_linkedin_note", args)

    async def draft_cover_letter(
        self, jd_text: str, tailored_resume_json: dict, tone: str = "conversational"
    ) -> dict:
        return await self.call_tool(
            "draft_cover_letter",
            {"jd_text": jd_text, "tailored_resume_json": tailored_resume_json, "tone": tone},
        )

    async def personalise_outreach(
        self,
        linkedin_note: str,
        cover_letter: str,
        company_context: str,
        job_id: str | None = None,
    ) -> dict:
        args: dict = {
            "linkedin_note": linkedin_note,
            "cover_letter": cover_letter,
            "company_context": company_context,
        }
        if job_id:
            args["job_id"] = job_id
        return await self.call_tool("personalise_outreach", args)

    async def draft_all(self, job: dict, resume_json: dict) -> dict:
        jd_text = job.get("jd_text", "")
        company = job.get("company", "")
        summary = resume_json.get("summary", "")

        note_task = self.draft_linkedin_note(jd_text, company, summary)
        letter_task = self.draft_cover_letter(jd_text, resume_json)
        import asyncio
        note, letter = await asyncio.gather(note_task, letter_task)
        return {"linkedin_note": note, "cover_letter": letter}


outreach_client = OutreachClient()
