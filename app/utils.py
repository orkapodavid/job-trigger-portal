import logging
from datetime import datetime, timedelta, timezone
from dateutil.relativedelta import relativedelta
from typing import Optional, Tuple
import pytz
from app.models import ScheduledJob

logger = logging.getLogger("Utils")

# Hong Kong Timezone
HKT = pytz.timezone("Asia/Hong_Kong")


def hkt_to_utc_schedule(
    schedule_type: str, time_str: Optional[str], day_val: Optional[int]
) -> Tuple[Optional[str], Optional[int]]:
    """
    Convert HKT schedule time to UTC for storage.

    Args:
        schedule_type: Type of schedule (daily, weekly, monthly, interval, manual)
        time_str: Time in HH:MM format (HKT)
        day_val: Day value (weekday 0-6 for weekly, day 1-31 for monthly)

    Returns:
        Tuple of (utc_time_str, utc_day_val)
    """
    if not time_str:
        return (time_str, day_val)

    if schedule_type in ("interval", "manual", "hourly"):
        return (time_str, day_val)

    try:
        h, m = map(int, time_str.split(":"))
    except (ValueError, AttributeError):
        return (time_str, day_val)

    dt_hkt = None

    if schedule_type == "daily":
        dt_hkt = HKT.localize(datetime(2024, 1, 1, h, m, 0))
    elif schedule_type == "weekly":
        dt_hkt = HKT.localize(datetime(2024, 1, 1 + (day_val or 0), h, m, 0))
    elif schedule_type == "monthly":
        dt_hkt = HKT.localize(datetime(2024, 1, day_val or 1, h, m, 0))
    else:
        return (time_str, day_val)

    dt_utc = dt_hkt.astimezone(timezone.utc)
    new_time = dt_utc.strftime("%H:%M")
    new_day = None

    if schedule_type == "weekly":
        new_day = dt_utc.weekday()
    elif schedule_type == "monthly":
        new_day = dt_utc.day

    return (new_time, new_day)


def utc_to_hkt_schedule(
    schedule_type: str, time_str: Optional[str], day_val: Optional[int]
) -> Tuple[Optional[str], Optional[int]]:
    """
    Convert UTC schedule time to HKT for display.

    Args:
        schedule_type: Type of schedule (daily, weekly, monthly, interval, manual)
        time_str: Time in HH:MM format (UTC)
        day_val: Day value (weekday 0-6 for weekly, day 1-31 for monthly)

    Returns:
        Tuple of (hkt_time_str, hkt_day_val)
    """
    if not time_str:
        return (time_str, day_val)

    if schedule_type in ("interval", "manual", "hourly"):
        return (time_str, day_val)

    try:
        h, m = map(int, time_str.split(":"))
    except (ValueError, AttributeError):
        return (time_str, day_val)

    dt_utc = None

    if schedule_type == "daily":
        dt_utc = datetime(2024, 1, 1, h, m, 0, tzinfo=timezone.utc)
    elif schedule_type == "weekly":
        dt_utc = datetime(2024, 1, 1 + (day_val or 0), h, m, 0, tzinfo=timezone.utc)
    elif schedule_type == "monthly":
        dt_utc = datetime(2024, 1, day_val or 1, h, m, 0, tzinfo=timezone.utc)
    else:
        return (time_str, day_val)

    dt_hkt = dt_utc.astimezone(HKT)
    new_time = dt_hkt.strftime("%H:%M")
    new_day = None

    if schedule_type == "weekly":
        new_day = dt_hkt.weekday()
    elif schedule_type == "monthly":
        new_day = dt_hkt.day

    return (new_time, new_day)


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
            if ":" in job.schedule_time:
                parts = job.schedule_time.split(":")
                hour = int(parts[0])
                minute = int(parts[1]) if len(parts) > 1 else 0
            else:
                # For hourly schedules, schedule_time may be just the minute
                minute = int(job.schedule_time)
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
