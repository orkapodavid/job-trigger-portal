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
        interval_seconds: How often the job should run in seconds.
        is_active: Whether the job is currently enabled.
        next_run: The calculated timestamp for the next scheduled execution.
    """

    __tablename__ = "scheduled_jobs"
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True, nullable=False)
    script_path: str = Field(nullable=False)
    interval_seconds: int = Field(nullable=False)
    is_active: bool = Field(default=True, nullable=False)
    next_run: Optional[datetime] = Field(
        default=None, sa_column_kwargs={"nullable": True}
    )
    logs: list["JobExecutionLog"] = Relationship(back_populates="job")


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