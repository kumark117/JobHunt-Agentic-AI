"""
Base MCP client — wraps stdio_client + ClientSession for tool calls.
Each call launches the server subprocess, calls the tool, and exits.
Per-request subprocess is intentional (see spec §13.1).
"""
import json
import os
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


SERVERS_DIR = Path(__file__).parent.parent / "mcp_servers"


class BaseMCPClient:
    def __init__(self, server_filename: str):
        self.server_path = str(SERVERS_DIR / server_filename)
        self.server_params = StdioServerParameters(
            command="python",
            args=[self.server_path],
            env={**os.environ},
        )

    async def call_tool(self, tool_name: str, arguments: dict) -> dict:
        async with stdio_client(self.server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(tool_name, arguments)
                if result.content:
                    raw = result.content[0].text
                    try:
                        return json.loads(raw)
                    except json.JSONDecodeError:
                        return {"raw": raw}
                return {}

    async def list_tools(self) -> list:
        async with stdio_client(self.server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.list_tools()
                return [t.name for t in result.tools]
