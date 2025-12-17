import asyncio
import logging
from datetime import datetime, timezone
from sqlmodel import Session, select, create_engine
from app.models import ScheduledJob, get_db_url
from app.utils import calculate_next_run
from app.websocket_server import dispatch_job_to_worker

logger = logging.getLogger("Scheduler")


async def run_scheduler():
    """
    Main scheduler loop.
    Checks for due jobs and dispatches them to available workers.
    """
    logger.info("Scheduler background task started.")
    engine = create_engine(get_db_url())
    while True:
        try:
            now = datetime.now(timezone.utc)
            with Session(engine) as session:
                query = (
                    select(ScheduledJob)
                    .where(ScheduledJob.is_active == True)
                    .where(ScheduledJob.next_run != None)
                    .where(ScheduledJob.next_run <= now)
                )
                due_jobs = session.exec(query).all()
                for job in due_jobs:
                    logger.info(
                        f"Job '{job.name}' (ID: {job.id}) is due. Attempting dispatch..."
                    )
                    dispatched = await dispatch_job_to_worker(job.id, job.script_path)
                    if dispatched:
                        next_run = calculate_next_run(job)
                        job.next_run = next_run
                        session.add(job)
                        session.commit()
                        logger.info(
                            f"Job '{job.name}' dispatched. Next run scheduled for: {next_run}"
                        )
                    else:
                        logger.warning(
                            f"Failed to dispatch job '{job.name}' (No workers available). Will retry next cycle."
                        )
        except Exception as e:
            logger.exception(f"Error in scheduler loop: {e}")
        await asyncio.sleep(10)
