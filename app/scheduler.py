from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.database import SessionLocal
from app.fetcher import run_all_sources

scheduler = AsyncIOScheduler(timezone="UTC")


async def scheduled_fetch() -> None:
    db = SessionLocal()
    try:
        await run_all_sources(db)
    finally:
        db.close()


def start_scheduler() -> None:
    if scheduler.running:
        return
    scheduler.add_job(scheduled_fetch, CronTrigger(hour=2, minute=0), id="daily_fetch", replace_existing=True)
    scheduler.start()


def stop_scheduler() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)
