"""
Standalone Worker Service (Database-Driven)

This service runs independently and handles:
1. Registering worker in WorkerRegistration table
2. Polling JobDispatch table for PENDING jobs
3. Claiming jobs via optimistic locking
4. Executing scripts and reporting results
5. Sending heartbeat updates
"""
import asyncio
import logging
import os
import platform
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from sqlmodel import Session, select, create_engine
from app.models import (
    WorkerRegistration,
    JobDispatch,
    JobExecutionLog,
    ScheduledJob,
    get_db_url,
)

# Configuration
WORKER_POLL_INTERVAL = int(os.getenv("WORKER_POLL_INTERVAL", "5"))  # seconds
WORKER_MAX_POLL_INTERVAL = int(os.getenv("WORKER_MAX_POLL_INTERVAL", "60"))  # seconds
WORKER_HEARTBEAT_INTERVAL = int(os.getenv("WORKER_HEARTBEAT_INTERVAL", "30"))  # seconds
WORKER_JOB_TIMEOUT = int(os.getenv("WORKER_JOB_TIMEOUT", "600"))  # 10 minutes

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("WorkerService")

# Worker state
WORKER_ID = f"worker-{uuid.uuid4().hex[:8]}"
START_TIME = datetime.now(timezone.utc)
JOBS_PROCESSED = 0
RUNNING = True


def register_worker(session: Session):
    """Register worker in database."""
    worker = WorkerRegistration(
        worker_id=WORKER_ID,
        hostname=platform.node(),
        platform=platform.system(),
        started_at=START_TIME,
        last_heartbeat=datetime.now(timezone.utc),
        status="IDLE",
        jobs_processed=0,
        process_id=os.getpid(),
    )
    
    # Check if worker already exists (shouldn't happen, but handle gracefully)
    existing = session.get(WorkerRegistration, WORKER_ID)
    if existing:
        logger.warning(f"Worker {WORKER_ID} already registered, updating...")
        session.delete(existing)
        session.commit()
    
    session.add(worker)
    session.commit()
    logger.info(f"Worker {WORKER_ID} registered successfully")


def update_heartbeat(session: Session, status: str = "IDLE", current_job_id: int = None):
    """Update worker heartbeat and status."""
    worker = session.get(WorkerRegistration, WORKER_ID)
    if worker:
        worker.last_heartbeat = datetime.now(timezone.utc)
        worker.status = status
        worker.jobs_processed = JOBS_PROCESSED
        worker.current_job_id = current_job_id
        session.add(worker)
        session.commit()
        logger.debug(f"Heartbeat updated: status={status}, jobs_processed={JOBS_PROCESSED}")
    else:
        logger.warning(f"Worker {WORKER_ID} not found in database, re-registering...")
        register_worker(session)


def claim_job(session: Session) -> tuple[JobDispatch, ScheduledJob] | None:
    """
    Attempt to claim a PENDING job using optimistic locking.
    
    Returns: (JobDispatch, ScheduledJob) tuple if claim succeeds, None otherwise
    """
    # Query for oldest PENDING job
    pending_job = session.exec(
        select(JobDispatch)
        .where(JobDispatch.status == "PENDING")
        .order_by(JobDispatch.created_at)
    ).first()
    
    if not pending_job:
        return None
    
    # Attempt to claim the job (optimistic locking)
    dispatch_id = pending_job.id
    now = datetime.now(timezone.utc)
    
    # Use raw SQL to ensure atomicity
    result = session.exec(
        select(JobDispatch)
        .where(JobDispatch.id == dispatch_id)
        .where(JobDispatch.status == "PENDING")
    ).first()
    
    if result:
        result.status = "IN_PROGRESS"
        result.worker_id = WORKER_ID
        result.claimed_at = now
        session.add(result)
        session.commit()
        session.refresh(result)
        
        # Get the associated job
        job = session.get(ScheduledJob, result.job_id)
        
        logger.info(f"Claimed job dispatch {dispatch_id} (job_id={result.job_id}, job_name='{job.name if job else 'Unknown'}')")
        return (result, job)
    else:
        logger.debug(f"Failed to claim dispatch {dispatch_id} - already claimed by another worker")
        return None


def execute_job(dispatch: JobDispatch, job: ScheduledJob) -> tuple[str, str]:
    """
    Execute the job script and return (status, log_output).
    
    Returns: ("SUCCESS"|"FAILURE"|"ERROR", log_output)
    """
    script_path = job.script_path
    logger.info(f"Executing job {job.id} ({job.name}): {script_path}")
    
    if not os.path.exists(script_path):
        error_msg = f"Script not found: {script_path}"
        logger.error(error_msg)
        return ("ERROR", error_msg)
    
    try:
        # Determine command based on file extension
        cmd = [script_path]
        if script_path.endswith(".py"):
            cmd = [sys.executable, script_path]
        elif script_path.endswith(".sh"):
            cmd = ["/bin/bash", script_path]
        elif script_path.endswith(".bat"):
            cmd = ["cmd.exe", "/c", script_path]
        
        # Execute with timeout
        process = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=WORKER_JOB_TIMEOUT
        )
        
        log_output = f"STDOUT:\n{process.stdout}\n\nSTDERR:\n{process.stderr}"
        
        if process.returncode == 0:
            logger.info(f"Job {job.id} completed successfully")
            return ("SUCCESS", log_output)
        else:
            logger.warning(f"Job {job.id} failed with exit code {process.returncode}")
            log_output += f"\n\nExit Code: {process.returncode}"
            return ("FAILURE", log_output)
            
    except subprocess.TimeoutExpired:
        error_msg = f"Execution timed out after {WORKER_JOB_TIMEOUT} seconds"
        logger.error(f"Job {job.id} timed out")
        return ("FAILURE", error_msg)
    except Exception as e:
        error_msg = f"Execution error: {str(e)}"
        logger.exception(f"Job {job.id} error: {e}")
        return ("ERROR", error_msg)


def report_job_result(session: Session, dispatch: JobDispatch, job: ScheduledJob, status: str, log_output: str):
    """
    Report job execution results to database.
    
    Updates JobDispatch status and creates JobExecutionLog entry.
    """
    global JOBS_PROCESSED
    
    now = datetime.now(timezone.utc)
    
    # Update dispatch record
    dispatch.status = "COMPLETED" if status == "SUCCESS" else "FAILED"
    dispatch.completed_at = now
    if status != "SUCCESS":
        dispatch.error_message = log_output[:500]  # Store first 500 chars of error
    session.add(dispatch)
    
    # Create execution log
    log_entry = JobExecutionLog(
        job_id=job.id,
        run_time=dispatch.claimed_at or now,
        status=status,
        log_output=log_output,
    )
    session.add(log_entry)
    
    # Commit changes
    session.commit()
    
    JOBS_PROCESSED += 1
    logger.info(f"Reported result for job {job.id}: {status}")


async def heartbeat_task(engine):
    """Background task to update heartbeat every N seconds."""
    while RUNNING:
        try:
            with Session(engine) as session:
                update_heartbeat(session, status="IDLE")
        except Exception as e:
            logger.error(f"Heartbeat update failed: {e}")
        
        await asyncio.sleep(WORKER_HEARTBEAT_INTERVAL)


async def job_polling_loop(engine):
    """Main job polling and execution loop."""
    poll_interval = WORKER_POLL_INTERVAL
    
    logger.info("Worker service started")
    logger.info(f"Configuration: poll_interval={WORKER_POLL_INTERVAL}s, "
                f"max_poll_interval={WORKER_MAX_POLL_INTERVAL}s, "
                f"heartbeat_interval={WORKER_HEARTBEAT_INTERVAL}s")
    
    while RUNNING:
        try:
            with Session(engine) as session:
                # Try to claim a job
                result = claim_job(session)
                
                if result:
                    dispatch, job = result
                    
                    # Reset poll interval to fast polling
                    poll_interval = WORKER_POLL_INTERVAL
                    
                    # Update status to BUSY
                    update_heartbeat(session, status="BUSY", current_job_id=job.id)
                    
                    # Execute job (outside of session to avoid long-held connections)
                    status, log_output = execute_job(dispatch, job)
                    
                    # Report results
                    with Session(engine) as result_session:
                        # Re-fetch dispatch in new session
                        dispatch = result_session.get(JobDispatch, dispatch.id)
                        job = result_session.get(ScheduledJob, job.id)
                        report_job_result(result_session, dispatch, job, status, log_output)
                        
                        # Update status back to IDLE
                        update_heartbeat(result_session, status="IDLE")
                else:
                    # No jobs available, apply exponential backoff
                    logger.debug(f"No jobs available, sleeping {poll_interval}s")
                    await asyncio.sleep(poll_interval)
                    poll_interval = min(poll_interval * 1.5, WORKER_MAX_POLL_INTERVAL)
                    
        except Exception as e:
            logger.error(f"Error in job polling loop: {e}", exc_info=True)
            await asyncio.sleep(WORKER_POLL_INTERVAL)


def cleanup_worker(engine):
    """Cleanup worker registration on shutdown."""
    global RUNNING
    RUNNING = False
    
    try:
        with Session(engine) as session:
            # Release any IN_PROGRESS jobs
            stuck_dispatches = session.exec(
                select(JobDispatch)
                .where(JobDispatch.worker_id == WORKER_ID)
                .where(JobDispatch.status == "IN_PROGRESS")
            ).all()
            
            for dispatch in stuck_dispatches:
                logger.warning(f"Releasing stuck dispatch {dispatch.id} back to PENDING")
                dispatch.status = "PENDING"
                dispatch.worker_id = None
                dispatch.claimed_at = None
                session.add(dispatch)
            
            # Remove worker registration
            worker = session.get(WorkerRegistration, WORKER_ID)
            if worker:
                session.delete(worker)
            
            session.commit()
            logger.info(f"Worker {WORKER_ID} cleaned up successfully")
            
    except Exception as e:
        logger.error(f"Error during worker cleanup: {e}", exc_info=True)


async def main_async(engine):
    """Main async entry point."""
    # Register worker
    with Session(engine) as session:
        register_worker(session)
    
    # Start heartbeat task
    heartbeat = asyncio.create_task(heartbeat_task(engine))
    
    # Run job polling loop
    try:
        await job_polling_loop(engine)
    finally:
        heartbeat.cancel()
        cleanup_worker(engine)


def main():
    """Entry point for the worker service."""
    logger.info(f"Initializing worker service (ID: {WORKER_ID})...")
    
    # Create database engine
    db_url = get_db_url()
    logger.info(f"Connecting to database: {db_url}")
    engine = create_engine(db_url)
    
    # Run worker service
    try:
        asyncio.run(main_async(engine))
    except KeyboardInterrupt:
        logger.info("Worker service stopped by user")
    except Exception as e:
        logger.error(f"Worker service crashed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
