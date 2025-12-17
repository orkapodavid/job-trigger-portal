import reflex as rx
from sqlmodel import Field, Relationship, SQLModel, create_engine
from sqlalchemy import Column, Text
from datetime import datetime, timezone
from typing import Optional
import os
import logging


def get_utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ScheduledJob(SQLModel, table=True):
    """
    Model representing a scheduled job trigger.

    Attributes:
        name: The display name of the job.
        script_path: The filesystem path to the script to execute.
        interval_seconds: How often the job should run in seconds (used if schedule_type is 'interval').
        schedule_type: The type of schedule ('interval', 'hourly', 'daily', 'weekly', 'monthly', 'manual').
        is_active: Whether the job is currently enabled.
        next_run: The calculated timestamp for the next scheduled execution. None for manual jobs not currently queued.
        last_dispatched_at: Timestamp of last dispatch creation (audit trail).
        dispatch_lock_until: Prevent redispatch until this time (prevents duplicate dispatches).
    """

    __tablename__ = "scheduled_jobs"
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True, nullable=False)
    script_path: str = Field(nullable=False)
    interval_seconds: int = Field(nullable=False)
    schedule_type: str = Field(default="interval", nullable=False)
    schedule_time: Optional[str] = Field(default=None, nullable=True)
    schedule_day: Optional[int] = Field(default=None, nullable=True)
    is_active: bool = Field(default=True, nullable=False)
    next_run: Optional[datetime] = Field(
        default=None, sa_column_kwargs={"nullable": True}
    )
    last_dispatched_at: Optional[datetime] = Field(default=None, nullable=True)
    dispatch_lock_until: Optional[datetime] = Field(default=None, nullable=True)
    logs: list["JobExecutionLog"] = Relationship(back_populates="job")


class WorkerRegistration(SQLModel, table=True):
    """
    Model representing registered workers and their health status.

    Attributes:
        worker_id: Unique worker identifier.
        hostname: Server hostname.
        platform: OS platform (Windows/Linux/Mac).
        started_at: Worker process start time.
        last_heartbeat: Last heartbeat timestamp.
        status: Worker status (IDLE, BUSY, OFFLINE).
        jobs_processed: Total jobs processed by this worker.
        current_job_id: Job currently being executed.
        process_id: OS process ID.
    """

    __tablename__ = "worker_registration"
    worker_id: str = Field(primary_key=True, max_length=50)
    hostname: str = Field(nullable=False, max_length=255)
    platform: str = Field(nullable=False, max_length=50)
    started_at: datetime = Field(default_factory=get_utc_now, nullable=False)
    last_heartbeat: datetime = Field(default_factory=get_utc_now, nullable=False)
    status: str = Field(default="IDLE", nullable=False, max_length=20)
    jobs_processed: int = Field(default=0, nullable=False)
    current_job_id: Optional[int] = Field(default=None, nullable=True)
    process_id: Optional[int] = Field(default=None, nullable=True)


class JobDispatch(SQLModel, table=True):
    """
    Model representing job dispatch queue and execution tracking.

    Attributes:
        id: Unique dispatch ID.
        job_id: Foreign key to ScheduledJob.
        created_at: When dispatch was created.
        claimed_at: When worker claimed job.
        completed_at: When execution finished.
        status: Dispatch status (PENDING, IN_PROGRESS, COMPLETED, FAILED, TIMEOUT).
        worker_id: Worker that claimed/executed job.
        retry_count: Number of retry attempts.
        error_message: Error details if failed.
    """

    __tablename__ = "job_dispatch"
    id: Optional[int] = Field(default=None, primary_key=True)
    job_id: int = Field(foreign_key="scheduled_jobs.id", index=True, nullable=False)
    created_at: datetime = Field(default_factory=get_utc_now, nullable=False, index=True)
    claimed_at: Optional[datetime] = Field(default=None, nullable=True, index=True)
    completed_at: Optional[datetime] = Field(default=None, nullable=True)
    status: str = Field(default="PENDING", nullable=False, max_length=20, index=True)
    worker_id: Optional[str] = Field(default=None, nullable=True, max_length=50, index=True)
    retry_count: int = Field(default=0, nullable=False)
    error_message: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))


class JobExecutionLog(SQLModel, table=True):
    """
    Model representing the execution history of a scheduled job.

    Attributes:
        job_id: Foreign key reference to the ScheduledJob.
        run_time: Timestamp when the execution started/occurred.
        status: The outcome status (e.g., 'success', 'failure', 'running').
        log_output: The captured stdout/stderr from the script execution.
    """

    __tablename__ = "job_execution_logs"
    id: Optional[int] = Field(default=None, primary_key=True)
    job_id: int = Field(foreign_key="scheduled_jobs.id", index=True, nullable=False)
    run_time: datetime = Field(default_factory=get_utc_now, nullable=False)
    status: str = Field(nullable=False)
    log_output: str = Field(default="", sa_column=Column(Text, nullable=True))
    job: Optional[ScheduledJob] = Relationship(back_populates="logs")


def get_db_url() -> str:
    """
    Retrieve the database URL from the environment or return a default SQLite path.

    This helper is critical for the decoupled worker script to access the same
    database as the Reflex web application.
    """
    return os.getenv("REFLEX_DB_URL", "sqlite:///reflex.db")


def init_db():
    """
    Initialize the database schema.

    This function creates all tables defined in the SQLModel metadata.
    It is intended to be used by the independent worker script or manual setup tools
    to ensure the schema exists before operations begin.
    """
    try:
        engine = create_engine(get_db_url(), echo=True)
        SQLModel.metadata.create_all(engine)
        print("Database tables created successfully.")
    except Exception as e:
        logging.exception(f"Error initializing database: {e}")
