from fastapi import APIRouter
from pydantic import BaseModel

from settings_loader import get_all_settings, set_setting

router = APIRouter()


class SettingsUpdate(BaseModel):
    tailor_mode: str | None = None
    fit_score_threshold: int | None = None
    max_tailor_retries: int | None = None
    discovery_sources: dict | None = None
    target_roles: list[str] | None = None
    target_locations: list[str] | None = None


@router.get("/")
async def get_settings():
    return await get_all_settings()


@router.post("/")
async def update_settings(body: SettingsUpdate):
    import json

    updates = body.model_dump(exclude_none=True)
    for key, value in updates.items():
        str_value = json.dumps(value) if not isinstance(value, str) else value
        await set_setting(key, str_value)

    return {"status": "saved", "updated": list(updates.keys())}
