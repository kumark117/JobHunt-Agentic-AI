from mcp_clients.base_client import BaseMCPClient


class ScoringClient(BaseMCPClient):
    def __init__(self):
        super().__init__("scoring_mcp_server.py")

    async def score_fit(self, jd_text: str, resume_json: dict) -> dict:
        return await self.call_tool("score_fit", {"jd_text": jd_text, "resume_json": resume_json})

    async def explain_score(
        self, fit_summary: dict, job_title: str = "", company: str = ""
    ) -> dict:
        return await self.call_tool(
            "explain_score",
            {"fit_summary": fit_summary, "job_title": job_title, "company": company},
        )

    async def filter_batch(self, scores: list[dict], threshold: int = 65) -> list[str]:
        result = await self.call_tool("filter_batch", {"scores": scores, "threshold": threshold})
        return result if isinstance(result, list) else []

    async def suggest_keywords(self, jd_text: str, resume_keywords: list[str] | None = None) -> dict:
        return await self.call_tool(
            "suggest_keywords",
            {"jd_text": jd_text, "resume_keywords": resume_keywords or []},
        )


scoring_client = ScoringClient()
