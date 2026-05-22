"""
In-process rate limiter for pipeline trigger endpoint.
Prevents double-triggering the same job within a cooldown window.
"""
from datetime import datetime, timedelta, timezone
from threading import Lock

_last_trigger: dict[str, datetime] = {}
_lock = Lock()

PIPELINE_COOLDOWN = timedelta(seconds=30)


def check_pipeline_cooldown(job_id: str) -> tuple[bool, int]:
    """
    Returns (allowed, retry_after_seconds).
    allowed=False means the job was triggered too recently.
    """
    now = datetime.now(timezone.utc)
    with _lock:
        last = _last_trigger.get(job_id)
        if last:
            elapsed = now - last
            if elapsed < PIPELINE_COOLDOWN:
                remaining = int((PIPELINE_COOLDOWN - elapsed).total_seconds())
                return False, remaining
        _last_trigger[job_id] = now
        return True, 0
