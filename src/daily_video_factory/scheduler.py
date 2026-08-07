from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from .config import Settings
from .logging import get_logger
from .pipeline import DailyVideoPipeline


def run_scheduler(settings: Settings) -> None:
    log = get_logger(component="scheduler")
    scheduler = BlockingScheduler(timezone=settings.channel.timezone)

    def daily_job() -> None:
        try:
            editorial_date = datetime.now(ZoneInfo(settings.channel.timezone)).date()
            DailyVideoPipeline(settings).run(editorial_date, resume=True)
        except Exception:
            log.exception("scheduled_run_failed")

    scheduler.add_job(
        daily_job,
        CronTrigger(hour=settings.schedule.hour, minute=settings.schedule.minute),
        id="one_daily_video",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
        misfire_grace_time=6 * 60 * 60 if settings.schedule.catch_up_if_missed else 60,
    )
    log.info(
        "scheduler_started",
        hour=settings.schedule.hour,
        minute=settings.schedule.minute,
        timezone=settings.channel.timezone,
    )
    scheduler.start()
