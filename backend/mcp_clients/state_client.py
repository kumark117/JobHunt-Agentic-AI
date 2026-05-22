from mcp_clients.base_client import BaseMCPClient


class StateClient(BaseMCPClient):
    def __init__(self):
        super().__init__("state_mcp_server.py")

    async def get_pipeline_state(self, job_id: str) -> dict:
        return await self.call_tool("get_pipeline_state", {"job_id": job_id})

    async def set_hitl_decision(
        self, job_id: str, gate: str, decision: str, feedback: str | None = None
    ) -> dict:
        args = {"job_id": job_id, "gate": gate, "decision": decision}
        if feedback:
            args["feedback"] = feedback
        return await self.call_tool("set_hitl_decision", args)

    async def list_pending_approvals(self, gate: str | None = None) -> list[dict]:
        args = {}
        if gate:
            args["gate"] = gate
        result = await self.call_tool("list_pending_approvals", args)
        return result if isinstance(result, list) else []

    async def update_job_status(self, job_id: str, status: str, notes: str | None = None) -> dict:
        args = {"job_id": job_id, "status": status}
        if notes:
            args["notes"] = notes
        return await self.call_tool("update_job_status", args)

    async def log_agent_step(
        self, job_id: str, agent: str, step: str, payload: dict | None = None
    ) -> dict:
        args = {"job_id": job_id, "agent": agent, "step": step}
        if payload:
            args["payload"] = payload
        return await self.call_tool("log_agent_step", args)


state_client = StateClient()
