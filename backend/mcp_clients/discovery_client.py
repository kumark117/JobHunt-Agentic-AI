from mcp_clients.base_client import BaseMCPClient


class DiscoveryClient(BaseMCPClient):
    def __init__(self):
        super().__init__("discovery_mcp_server.py")

    async def search_jobs(
        self,
        keywords: list[str],
        platforms: list[str] | None = None,
        location: str = "Bangalore",
        days_back: int = 7,
    ) -> list[dict]:
        args: dict = {"keywords": keywords, "location": location, "days_back": days_back}
        if platforms:
            args["platforms"] = platforms
        result = await self.call_tool("search_jobs", args)
        return result if isinstance(result, list) else []

    async def fetch_jd_full(self, url: str) -> dict:
        return await self.call_tool("fetch_jd_full", {"url": url})

    async def check_company_careers(self, company_slug: str, careers_url: str) -> list[dict]:
        result = await self.call_tool(
            "check_company_careers",
            {"company_slug": company_slug, "careers_url": careers_url},
        )
        return result if isinstance(result, list) else []

    async def parse_hn_thread(self, month: str, year: str) -> list[dict]:
        result = await self.call_tool("parse_hn_thread", {"month": month, "year": year})
        return result if isinstance(result, list) else []


discovery_client = DiscoveryClient()
