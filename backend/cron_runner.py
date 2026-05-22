"""
Standalone cron runner — used by Render cron job service.
Run: python cron_runner.py
"""
import asyncio
import logging
import sys

logging.basicConfig(
    stream=sys.stdout,
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

from cron_scheduler import run_discovery_and_queue

if __name__ == "__main__":
    asyncio.run(run_discovery_and_queue())
