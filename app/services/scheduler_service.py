import asyncio
import logging
from datetime import datetime, timezone
from sqlmodel import Session, select, create_engine
from app.models import ScheduledJob, get_db_url
from app.websocket_server import dispatch_job_to_worker
from app.utils import calculate_next_run

logger = logging.getLogger("SchedulerService")
engine = create_engine(get_db_url())


async def run_scheduler():
    """
    Background task that polls for due jobs and dispatches them to workers.
    """
    logger.info("Scheduler service started.")
    while True:
        try:
            with Session(engine) as session:
                now = datetime.now(timezone.utc)
                statement = select(ScheduledJob).where(
                    ScheduledJob.is_active == True, ScheduledJob.next_run <= now
                )
                due_jobs = session.exec(statement).all()
                for job in due_jobs:
                    logger.info(f"Job {job.id} ({job.name}) is due. Dispatching...")
                    success = await dispatch_job_to_worker(
                        job.id, job.script_path, job.script_args
                    )
                    if success:
                        next_run = calculate_next_run(job)
                        job.next_run = next_run
                        session.add(job)
                        session.commit()
                        logger.info(
                            f"Job {job.id} dispatched successfully. Next run: {next_run}"
                        )
                    else:
                        logger.warning(
                            f"Failed to dispatch job {job.id}. No available workers."
                        )
        except Exception as e:
            logger.exception(f"Error in scheduler loop: {e}")
        await asyncio.sleep(10)