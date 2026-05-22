from mcp_clients.base_client import BaseMCPClient


class TailorClient(BaseMCPClient):
    def __init__(self):
        super().__init__("tailor_mcp_server.py")

    async def tailor_resume(
        self, jd_text: str, resume_json: dict, feedback: str | None = None
    ) -> dict:
        args: dict = {"jd_text": jd_text, "resume_json": resume_json}
        if feedback:
            args["feedback"] = feedback
        return await self.call_tool("tailor_resume", args)

    async def diff_resume(self, original_json: dict, tailored_json: dict) -> dict:
        return await self.call_tool(
            "diff_resume",
            {"original_json": original_json, "tailored_json": tailored_json},
        )

    async def retry_tailor(
        self, jd_text: str, resume_json: dict, rejection_note: str, attempt_n: int = 2
    ) -> dict:
        return await self.call_tool(
            "retry_tailor",
            {
                "jd_text": jd_text,
                "resume_json": resume_json,
                "rejection_note": rejection_note,
                "attempt_n": attempt_n,
            },
        )

    async def export_resume_pdf(self, tailored_json: dict, job_id: str) -> dict:
        return await self.call_tool(
            "export_resume_pdf",
            {"tailored_json": tailored_json, "job_id": job_id},
        )


tailor_client = TailorClient()
