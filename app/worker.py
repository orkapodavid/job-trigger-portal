import time
import subprocess
import sys
import os
import logging
import signal
from datetime import datetime, timedelta
from typing import Optional
from sqlmodel import Session, select, create_engine

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)
from app.models import ScheduledJob, JobExecutionLog, get_db_url, init_db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("JobWorker")
running = True


def handle_signal(signum, frame):
    global running
    logger.info("Received termination signal. Shutting down gracefully...")
    running = False


def run_job(job: ScheduledJob, engine) -> None:
    logger.info(f"Starting execution of job: {job.name} (ID: {job.id})")
    start_time = datetime.utcnow()
    status = "RUNNING"
    log_output = ""
    script_path = job.script_path
    interval_seconds = job.interval_seconds
    job_id = job.id
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
    with Session(engine) as session:
        current_job = session.get(ScheduledJob, job_id)
        if current_job:
            next_run = datetime.utcnow() + timedelta(seconds=interval_seconds)
            current_job.next_run = next_run
            session.add(current_job)
            execution_log = JobExecutionLog(
                job_id=job_id, run_time=start_time, status=status, log_output=log_output
            )
            session.add(execution_log)
            try:
                session.commit()
                logger.info(
                    f"Job {current_job.name} finished with status {status}. Next run: {next_run}"
                )
            except Exception as e:
                logger.exception(f"Failed to commit transaction for job {job_id}: {e}")
        else:
            logger.warning(f"Job {job_id} no longer exists in database.")


def main():
    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)
    init_db()
    db_url = get_db_url()
    engine = create_engine(db_url)
    logger.info(f"Worker started. Polling database at {db_url}")
    while running:
        try:
            with Session(engine) as session:
                now = datetime.utcnow()
                query = (
                    select(ScheduledJob)
                    .where(ScheduledJob.is_active == True)
                    .where(
                        (ScheduledJob.next_run <= now) | (ScheduledJob.next_run == None)
                    )
                )
                jobs = session.exec(query).all()
                for job in jobs:
                    if not running:
                        break
                    run_job(job, engine)
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