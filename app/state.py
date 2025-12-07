import reflex as rx
import asyncio
import logging
import os
from sqlmodel import Session, select, desc, create_engine
from typing import Optional
from datetime import datetime
from app.models import ScheduledJob, JobExecutionLog, get_db_url, init_db

engine = create_engine(get_db_url())


class State(rx.State):
    """
    Main state for the Job Trigger Portal.
    Manages job CRUD, log viewing, and periodic updates.
    """

    jobs: list[dict] = []
    logs: list[JobExecutionLog] = []
    selected_job_id: Optional[int] = None
    selected_job_name: str = ""
    selected_log_entry: Optional[JobExecutionLog] = None
    new_job_name: str = ""
    new_job_script_path: str = ""
    new_job_interval_value: str = "1"
    new_job_interval_unit: str = "Hours"
    is_loading: bool = False
    search_query: str = ""
    auto_refresh: bool = True
    log_limit: int = 50
    is_modal_open: bool = False

    @rx.event
    def set_modal_open(self, value: bool):
        self.is_modal_open = value

    @rx.event
    def load_jobs(self):
        """Fetch all scheduled jobs from the database."""
        try:
            with Session(engine) as session:
                query = select(ScheduledJob)
                if self.search_query:
                    query = query.where(ScheduledJob.name.contains(self.search_query))
                query = query.order_by(ScheduledJob.id)
                results = session.exec(query).all()
                self.jobs = []
                for job in results:
                    job_dict = job.model_dump()
                    seconds = job.interval_seconds
                    if seconds >= 86400 and seconds % 86400 == 0:
                        val = seconds // 86400
                        unit = "Day" if val == 1 else "Days"
                    elif seconds >= 3600 and seconds % 3600 == 0:
                        val = seconds // 3600
                        unit = "Hour" if val == 1 else "Hours"
                    elif seconds >= 60 and seconds % 60 == 0:
                        val = seconds // 60
                        unit = "Minute" if val == 1 else "Minutes"
                    else:
                        val = seconds
                        unit = "Second" if val == 1 else "Seconds"
                    job_dict["formatted_interval"] = f"{val} {unit}"
                    self.jobs.append(job_dict)
        except Exception as e:
            logging.exception(f"Error loading jobs: {e}")

    @rx.event
    def run_job_now(self, job_id: int):
        """Force a job to run immediately by updating its next_run time."""
        try:
            with Session(engine) as session:
                job = session.get(ScheduledJob, job_id)
                if job:
                    if not job.is_active:
                        return rx.toast.error(
                            "Cannot run inactive job. Please activate it first."
                        )
                    job.next_run = datetime.utcnow()
                    session.add(job)
                    session.commit()
                    return rx.toast.info(
                        f"Queued '{job.name}' for immediate execution."
                    )
            self.load_jobs()
        except Exception as e:
            logging.exception(f"Error running job {job_id}: {e}")
            return rx.toast.error(f"Failed to run job: {e}")

    @rx.event
    def add_job(self):
        """Create a new scheduled job."""
        if not self.new_job_name or not self.new_job_script_path:
            return rx.window_alert("Name and Script Path are required.")
        if not os.path.exists(self.new_job_script_path):
            return rx.window_alert(
                f"Script not found at: {self.new_job_script_path}\nPlease ensure the file exists in the project root."
            )
        try:
            val = int(self.new_job_interval_value)
            if val < 1:
                raise ValueError
            multiplier = 1
            if self.new_job_interval_unit == "Minutes":
                multiplier = 60
            elif self.new_job_interval_unit == "Hours":
                multiplier = 3600
            elif self.new_job_interval_unit == "Days":
                multiplier = 86400
            interval_seconds = val * multiplier
        except ValueError as e:
            logging.exception(f"Invalid interval value: {e}")
            return rx.window_alert("Interval must be a positive integer.")
        try:
            with Session(engine) as session:
                new_job = ScheduledJob(
                    name=self.new_job_name,
                    script_path=self.new_job_script_path,
                    interval_seconds=interval_seconds,
                    is_active=True,
                    next_run=datetime.utcnow(),
                )
                session.add(new_job)
                session.commit()
                session.refresh(new_job)
            self.new_job_name = ""
            self.new_job_script_path = ""
            self.new_job_interval_value = "1"
            self.new_job_interval_unit = "Hours"
            self.is_modal_open = False
            self.load_jobs()
            return rx.window_alert(f"Job '{new_job.name}' created successfully.")
        except Exception as e:
            logging.exception(f"Error creating job: {e}")
            return rx.window_alert(f"Error creating job: {e}")

    @rx.event
    def toggle_job_status(self, job_id: int):
        """Toggle the active status of a job."""
        try:
            with Session(engine) as session:
                job = session.get(ScheduledJob, job_id)
                if job:
                    job.is_active = not job.is_active
                    if job.is_active:
                        job.next_run = datetime.utcnow()
                    session.add(job)
                    session.commit()
            self.load_jobs()
        except Exception as e:
            logging.exception(f"Error toggling job {job_id}: {e}")

    @rx.event
    def delete_job(self, job_id: int):
        """Delete a job and its logs."""
        try:
            with Session(engine) as session:
                job = session.get(ScheduledJob, job_id)
                if job:
                    logs = session.exec(
                        select(JobExecutionLog).where(JobExecutionLog.job_id == job_id)
                    ).all()
                    for log in logs:
                        session.delete(log)
                    session.delete(job)
                    session.commit()
            self.load_jobs()
            if self.selected_job_id == job_id:
                self.selected_job_id = None
                self.selected_log_entry = None
                self.logs = []
        except Exception as e:
            logging.exception(f"Error deleting job {job_id}: {e}")

    @rx.event
    def select_job(self, job_id: int):
        """Select a job to view its logs."""
        self.selected_job_id = job_id
        job = next((j for j in self.jobs if j["id"] == job_id), None)
        if job:
            self.selected_job_name = job["name"]
        self.selected_log_entry = None
        self.load_logs()

    @rx.event
    def select_log(self, log_id: int):
        """Select a specific log entry to view full details."""
        log = next((l for l in self.logs if l.id == log_id), None)
        if log:
            self.selected_log_entry = log

    @rx.event
    def load_logs(self):
        """Fetch logs for the selected job."""
        if self.selected_job_id is None:
            self.logs = []
            return
        try:
            with Session(engine) as session:
                query = (
                    select(JobExecutionLog)
                    .where(JobExecutionLog.job_id == self.selected_job_id)
                    .order_by(desc(JobExecutionLog.run_time))
                    .limit(self.log_limit)
                )
                self.logs = session.exec(query).all()
        except Exception as e:
            logging.exception(f"Error loading logs: {e}")

    @rx.event
    def set_search_query(self, query: str):
        self.search_query = query
        self.load_jobs()

    @rx.event(background=True)
    async def on_load(self):
        """Initial load and background refresh loop."""
        init_db()
        async with self:
            self.load_jobs()
        while True:
            await asyncio.sleep(5)
            async with self:
                if self.auto_refresh:
                    try:
                        self.load_jobs()
                        if self.selected_job_id:
                            self.load_logs()
                    except Exception as e:
                        logging.exception(f"Error in background refresh: {e}")
