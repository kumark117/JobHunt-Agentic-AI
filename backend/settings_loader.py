"""
Settings loader — DB values take precedence over config.json.
Use get_setting() anywhere in the FastAPI process.
"""
import json
import os
from pathlib import Path

from sqlalchemy import select

CONFIG_PATH = Path(__file__).parent / "config.json"

_config_cache: dict = {}


def _load_config() -> dict:
    global _config_cache
    if not _config_cache and CONFIG_PATH.exists():
        with open(CONFIG_PATH) as f:
            _config_cache = json.load(f)
    return _config_cache


async def get_setting(key: str, default=None):
    from db.session import AsyncSessionLocal
    from db.models import Setting

    try:
        async with AsyncSessionLocal() as session:
            result = await session.get(Setting, key)
            if result:
                return result.value
    except Exception:
        pass

    config = _load_config()
    return config.get(key, default)


async def set_setting(key: str, value: str):
    from db.session import AsyncSessionLocal
    from db.models import Setting
    from datetime import datetime, timezone

    async with AsyncSessionLocal() as session:
        existing = await session.get(Setting, key)
        if existing:
            existing.value = value
            existing.updated_at = datetime.now(timezone.utc)
        else:
            session.add(Setting(key=key, value=value))
        await session.commit()


async def get_all_settings() -> dict:
    from db.session import AsyncSessionLocal
    from db.models import Setting
    from sqlalchemy import select

    config = _load_config()
    result = {}
    try:
        async with AsyncSessionLocal() as session:
            rows = await session.execute(select(Setting))
            for row in rows.scalars():
                result[row.key] = row.value
    except Exception:
        pass

    return {**config, **result}
