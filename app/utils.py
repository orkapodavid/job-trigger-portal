import logging
from datetime import datetime, timedelta, timezone
from dateutil.relativedelta import relativedelta
from typing import Optional
from app.models import ScheduledJob

logger = logging.getLogger("Utils")


def ensure_utc_aware(dt: Optional[datetime]) -> Optional[datetime]:
    """
    Convert any datetime to timezone-aware UTC datetime.
    
    Args:
        dt: A datetime object (naive or aware) or None
    
    Returns:
        A timezone-aware datetime in UTC, or None if input is None
    
    Behavior:
        - If input is None: returns None
        - If input is already timezone-aware: returns as-is
        - If input is timezone-naive: assumes UTC and adds timezone.utc
    
    This helper ensures all datetime arithmetic operations are safe
    when working with database-retrieved datetime objects that may
    lose timezone information (e.g., with SQLite backend).
    """
    if dt is None:
        return None
    if dt.tzinfo is not None and dt.tzinfo.utcoffset(dt) is not None:
        # Already timezone-aware
        return dt
    # Timezone-naive, assume UTC
    return dt.replace(tzinfo=timezone.utc)


def calculate_next_run(job: ScheduledJob) -> Optional[datetime]:
    """
    Calculate the next scheduled run time based on schedule configuration.
    Returns None for manual jobs, indicating they should not be automatically rescheduled.
    """
    if job.schedule_type == "manual":
        return None
    now = datetime.now(timezone.utc)
    if job.schedule_type == "interval" or not job.schedule_type:
        return now + timedelta(seconds=job.interval_seconds)
    hour = 0
    minute = 0
    if job.schedule_time:
        try:
            parts = job.schedule_time.split(":")
            hour = int(parts[0])
            minute = int(parts[1])
        except (ValueError, IndexError) as e:
            logger.exception(f"Error parsing schedule_time: {e}")
    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if job.schedule_type == "hourly":
        target = now.replace(minute=minute, second=0, microsecond=0)
        if target <= now:
            target += timedelta(hours=1)
    elif job.schedule_type == "daily":
        if target <= now:
            target += timedelta(days=1)
    elif job.schedule_type == "weekly":
        target_day = job.schedule_day if job.schedule_day is not None else 0
        current_weekday = target.weekday()
        days_ahead = target_day - current_weekday
        target = target + timedelta(days=days_ahead)
        if target <= now:
            target += timedelta(weeks=1)
    elif job.schedule_type == "monthly":
        target_day = job.schedule_day if job.schedule_day is not None else 1
        try:
            target = target + relativedelta(day=target_day)
        except ValueError as e:
            logger.exception(f"Error applying monthly schedule: {e}")
        if target <= now:
            target += relativedelta(months=1, day=target_day)
    return target
