import time
import subprocess
import sys
import os
import logging
import signal
import threading
from datetime import datetime, timedelta, timezone
from dateutil.relativedelta import relativedelta
from typing import Optional
from sqlmodel import Session, select, create_engine
from app.models import ScheduledJob, JobExecutionLog, get_db_url, init_db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("JobWorker")
running = True


def handle_signal(signum, frame):
    """Handle termination signals for graceful shutdown."""
    global running
    logger.info("Received termination signal. Shutting down gracefully...")
    running = False


def execute_job_thread(job_id: int, job_name: str, script_path: str, engine):
    """Execute the job script in a separate thread to prevent blocking."""
    logger.info(f"Starting execution thread for job: {job_name} (ID: {job_id})")
    start_time = datetime.now(timezone.utc)
    status = "RUNNING"
    log_output = ""
    try:
        if not os.path.exists(script_path):
            raise FileNotFoundError(f"Script not found at path: {script_path}")
        cmd = []
        if script_path.endswith(".py"):
            cmd = [sys.executable, script_path]
        elif script_path.endswith(".sh"):
            cmd = ["/bin/bash", script_path]
        else:
            cmd = [script_path]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        log_output = f"STDOUT:\n{result.stdout}\n\nSTDERR:\n{result.stderr}"
        if result.returncode == 0:
            status = "SUCCESS"
        else:
            status = "FAILURE"
            log_output += f"\n\nExit Code: {result.returncode}"
    except FileNotFoundError as e:
        status = "ERROR"
        log_output = f"System Error: {str(e)}"
        logger.exception(f"Job {job_id} failed: {e}")
    except subprocess.TimeoutExpired:
        status = "FAILURE"
        log_output = "Execution timed out after 300 seconds."
        logger.exception(f"Job {job_id} timed out.")
    except Exception as e:
        status = "ERROR"
        log_output = f"Unexpected Error: {str(e)}"
        logger.exception(f"Job {job_id} failed with unexpected error")
    try:
        with Session(engine) as session:
            execution_log = JobExecutionLog(
                job_id=job_id, run_time=start_time, status=status, log_output=log_output
            )
            session.add(execution_log)
            session.commit()
            logger.info(f"Job {job_name} execution finished with status {status}.")
    except Exception as e:
        logger.exception(f"Failed to save log for job {job_id}: {e}")


def calculate_next_run(job: ScheduledJob) -> datetime:
    """
    Calculate the next scheduled run time based on schedule configuration.
    """
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


def process_job(job: ScheduledJob, engine) -> None:
    """
    Schedule next run and spawn execution thread.

    Calculating next_run BEFORE execution eliminates drift caused by execution time.
    """
    try:
        with Session(engine) as session:
            current_job = session.get(ScheduledJob, job.id)
            if not current_job:
                logger.warning(f"Job {job.id} no longer exists, skipping.")
                return
            next_run = calculate_next_run(current_job)
            current_job.next_run = next_run
            session.add(current_job)
            session.commit()
            logger.info(f"Scheduled next run for '{current_job.name}' at {next_run}")
            job_id = current_job.id
            job_name = current_job.name
            script_path = current_job.script_path
    except Exception as e:
        logger.exception(f"Failed to update schedule for job {job.id}: {e}")
        return
    t = threading.Thread(
        target=execute_job_thread, args=(job_id, job_name, script_path, engine)
    )
    t.daemon = True
    t.start()


def main():
    """Main worker loop."""
    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)
    init_db()
    db_url = get_db_url()
    engine = create_engine(db_url)
    logger.info(f"Worker started. Polling database at {db_url}")
    while running:
        try:
            with Session(engine) as session:
                now = datetime.now(timezone.utc)
                query = (
                    select(ScheduledJob)
                    .where(ScheduledJob.is_active == True)
                    .where(
                        (ScheduledJob.next_run <= now) | (ScheduledJob.next_run == None)
                    )
                )
                jobs = session.exec(query).all()
                if not jobs:
                    pass
                for job in jobs:
                    if not running:
                        break
                    process_job(job, engine)
        except Exception as e:
            logger.exception(f"Error in main polling loop: {e}")
            time.sleep(5)
        sleep_duration = 5
        for _ in range(sleep_duration):
            if not running:
                break
            time.sleep(1)
    logger.info("Worker shutdown complete.")


if __name__ == "__main__":
    main()