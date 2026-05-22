"""
M4 — HITL Gate
asyncio.Future-based pause mechanism.
When the pipeline reaches a gate, it awaits the future — zero CPU cost.
The FastAPI /hitl endpoint resolves the future, resuming the pipeline instantly.
"""
import asyncio
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Decision:
    gate: str
    job_id: str
    decision: str                    # 'approved' | 'rejected' | 'skip' | 'override'
    feedback: Optional[str] = None
    manual_resume: Optional[dict] = None
    tailor_choice: Optional[str] = None  # 'tailor' | 'original' (gate1 tailor question)

    @property
    def approved(self) -> bool:
        return self.decision == "approved"

    @property
    def skip(self) -> bool:
        return self.decision == "skip"

    @property
    def override(self) -> bool:
        return self.decision == "override"


class HITLGate:
    def __init__(self):
        self._pending: dict[str, asyncio.Future] = {}

    async def wait_for_decision(self, gate: str, job_id: str) -> Decision:
        key = f"{gate}:{job_id}"
        loop = asyncio.get_event_loop()
        future: asyncio.Future[Decision] = loop.create_future()
        self._pending[key] = future
        try:
            return await future
        finally:
            self._pending.pop(key, None)

    def resolve(self, gate: str, job_id: str, decision: Decision) -> bool:
        key = f"{gate}:{job_id}"
        future = self._pending.get(key)
        if future and not future.done():
            future.set_result(decision)
            return True
        return False

    def cancel(self, gate: str, job_id: str):
        key = f"{gate}:{job_id}"
        future = self._pending.pop(key, None)
        if future and not future.done():
            future.cancel()

    def list_pending(self) -> list[str]:
        return list(self._pending.keys())


hitl_gate = HITLGate()
