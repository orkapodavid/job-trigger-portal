"""
Standalone Job Scheduler Service

This service runs independently from the Reflex web portal and handles:
1. Discovering due jobs from the database
2. Creating JobDispatch records for workers to claim
3. Monitoring stuck jobs and handling timeouts
4. Cleaning up completed dispatch records
"""
import asyncio
import logging
import sys
import os
from datetime import datetime, timezone, timedelta
from sqlmodel import Session, select, create_engine
from app.models import (
    ScheduledJob,
    JobDispatch,
    WorkerRegistration,
    JobExecutionLog,
    get_db_url,
)
from app.utils import calculate_next_run

# Configuration
SCHEDULER_POLL_INTERVAL = int(os.getenv("SCHEDULER_POLL_INTERVAL", "10"))  # seconds
DISPATCH_LOCK_DURATION = int(os.getenv("DISPATCH_LOCK_DURATION", "300"))  # 5 minutes
JOB_TIMEOUT_THRESHOLD = int(os.getenv("JOB_TIMEOUT_THRESHOLD", "600"))  # 10 minutes
MAX_RETRY_ATTEMPTS = int(os.getenv("MAX_RETRY_ATTEMPTS", "3"))
CLEANUP_RETENTION_DAYS = int(os.getenv("CLEANUP_RETENTION_DAYS", "30"))
WORKER_OFFLINE_THRESHOLD = int(os.getenv("WORKER_OFFLINE_THRESHOLD", "180"))  # 3 minutes

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("SchedulerService")


def cleanup_stale_workers(session: Session):
    """Mark workers as OFFLINE if they haven't sent heartbeat in threshold time."""
    now = datetime.now(timezone.utc)
    threshold = now - timedelta(seconds=WORKER_OFFLINE_THRESHOLD)
    
    stale_workers = session.exec(
        select(WorkerRegistration).where(WorkerRegistration.last_heartbeat < threshold)
    ).all()
    
    for worker in stale_workers:
        logger.info(f"Marking worker {worker.worker_id} as OFFLINE (last heartbeat: {worker.last_heartbeat})")
        session.delete(worker)
    
    if stale_workers:
        session.commit()
        logger.info(f"Cleaned up {len(stale_workers)} stale workers")


def detect_stuck_jobs(session: Session):
    """
    Detect jobs stuck in IN_PROGRESS state and handle them.
    
    A job is stuck if:
    - Status is IN_PROGRESS
    - claimed_at is older than JOB_TIMEOUT_THRESHOLD
    - Worker is OFFLINE or doesn't exist
    """
    now = datetime.now(timezone.utc)
    threshold = now - timedelta(seconds=JOB_TIMEOUT_THRESHOLD)
    
    stuck_dispatches = session.exec(
        select(JobDispatch)
        .where(JobDispatch.status == "IN_PROGRESS")
        .where(JobDispatch.claimed_at < threshold)
    ).all()
    
    for dispatch in stuck_dispatches:
        # Check if worker still exists
        worker = session.get(WorkerRegistration, dispatch.worker_id) if dispatch.worker_id else None
        
        if not worker:
            logger.warning(
                f"Job dispatch {dispatch.id} (job_id={dispatch.job_id}) stuck - "
                f"worker {dispatch.worker_id} offline. Marking as TIMEOUT."
            )
            
            # Update dispatch status
            dispatch.status = "TIMEOUT"
            dispatch.completed_at = now
            dispatch.error_message = f"Worker {dispatch.worker_id} died during execution"
            session.add(dispatch)
            
            # Create execution log
            log_entry = JobExecutionLog(
                job_id=dispatch.job_id,
                run_time=dispatch.claimed_at or now,
                status="TIMEOUT",
                log_output=f"Job timed out after {JOB_TIMEOUT_THRESHOLD}s. Worker {dispatch.worker_id} went offline.",
            )
            session.add(log_entry)
            
            # Retry if under retry limit
            if dispatch.retry_count < MAX_RETRY_ATTEMPTS:
                logger.info(f"Creating retry dispatch for job {dispatch.job_id} (attempt {dispatch.retry_count + 1})")
                retry_dispatch = JobDispatch(
                    job_id=dispatch.job_id,
                    status="PENDING",
                    retry_count=dispatch.retry_count + 1,
                )
                session.add(retry_dispatch)
            else:
                logger.warning(f"Job {dispatch.job_id} exceeded max retry attempts ({MAX_RETRY_ATTEMPTS})")
    
    if stuck_dispatches:
        session.commit()
        logger.info(f"Processed {len(stuck_dispatches)} stuck job dispatches")


def cleanup_old_dispatches(session: Session):
    """Remove completed/failed dispatch records older than retention period."""
    now = datetime.now(timezone.utc)
    threshold = now - timedelta(days=CLEANUP_RETENTION_DAYS)
    
    # Count old dispatches
    old_dispatches = session.exec(
        select(JobDispatch)
        .where(JobDispatch.status.in_(["COMPLETED", "FAILED", "TIMEOUT"]))
        .where(JobDispatch.completed_at < threshold)
    ).all()
    
    for dispatch in old_dispatches:
        session.delete(dispatch)
    
    if old_dispatches:
        session.commit()
        logger.info(f"Cleaned up {len(old_dispatches)} old dispatch records (older than {CLEANUP_RETENTION_DAYS} days)")


def dispatch_due_jobs(session: Session):
    """
    Find due jobs and create dispatch records for workers to claim.
    
    Uses database locking to prevent duplicate dispatches from multiple scheduler instances.
    """
    now = datetime.now(timezone.utc)
    
    # Query for due jobs with lock prevention
    query = (
        select(ScheduledJob)
        .where(ScheduledJob.is_active == True)
        .where(ScheduledJob.next_run != None)
        .where(ScheduledJob.next_run <= now)
        .where(
            (ScheduledJob.dispatch_lock_until == None) | 
            (ScheduledJob.dispatch_lock_until < now)
        )
    )
    
    due_jobs = session.exec(query).all()
    
    if not due_jobs:
        logger.debug(f"No due jobs found at {now.isoformat()}")
        return
    
    logger.info(f"Found {len(due_jobs)} due jobs to dispatch")
    
    for job in due_jobs:
        try:
            # Create dispatch record
            dispatch = JobDispatch(
                job_id=job.id,
                status="PENDING",
                retry_count=0,
            )
            session.add(dispatch)
            
            # Update job with lock and next_run
            next_run = calculate_next_run(job)
            job.next_run = next_run
            job.last_dispatched_at = now
            job.dispatch_lock_until = now + timedelta(seconds=DISPATCH_LOCK_DURATION)
            session.add(job)
            
            session.commit()
            session.refresh(dispatch)
            
            logger.info(
                f"Dispatched job '{job.name}' (ID: {job.id}, dispatch_id: {dispatch.id}). "
                f"Next run: {next_run.isoformat() if next_run else 'None (manual job)'}"
            )
            
        except Exception as e:
            logger.error(f"Error dispatching job {job.id}: {e}", exc_info=True)
            session.rollback()


async def scheduler_loop(engine):
    """Main scheduler loop."""
    iteration = 0
    logger.info("Scheduler service started")
    logger.info(f"Configuration: poll_interval={SCHEDULER_POLL_INTERVAL}s, "
                f"lock_duration={DISPATCH_LOCK_DURATION}s, "
                f"timeout_threshold={JOB_TIMEOUT_THRESHOLD}s")
    
    while True:
        iteration += 1
        try:
            logger.debug(f"Scheduler loop iteration {iteration}")
            
            with Session(engine) as session:
                # Dispatch due jobs
                dispatch_due_jobs(session)
                
                # Cleanup stale workers (every 10 iterations = ~100s)
                if iteration % 10 == 0:
                    cleanup_stale_workers(session)
                
                # Detect stuck jobs (every 6 iterations = ~60s)
                if iteration % 6 == 0:
                    detect_stuck_jobs(session)
                
                # Cleanup old dispatches (every 360 iterations = ~1 hour)
                if iteration % 360 == 0:
                    cleanup_old_dispatches(session)
                    
        except Exception as e:
            logger.error(f"Error in scheduler loop: {e}", exc_info=True)
        
        await asyncio.sleep(SCHEDULER_POLL_INTERVAL)


def main():
    """Entry point for the scheduler service."""
    logger.info("Initializing scheduler service...")
    
    # Create database engine
    db_url = get_db_url()
    logger.info(f"Connecting to database: {db_url}")
    engine = create_engine(db_url)
    
    # Run scheduler loop
    try:
        asyncio.run(scheduler_loop(engine))
    except KeyboardInterrupt:
        logger.info("Scheduler service stopped by user")
    except Exception as e:
        logger.error(f"Scheduler service crashed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
