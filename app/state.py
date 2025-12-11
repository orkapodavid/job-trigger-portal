import reflex as rx
import asyncio
import logging
import os
from sqlmodel import Session, select, desc, create_engine
from typing import Optional
from datetime import datetime, timezone
from app.models import ScheduledJob, JobExecutionLog, get_db_url, init_db

engine = create_engine(get_db_url())
SCRIPTS_DIR = os.path.join(os.getcwd(), "app", "scripts")


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
    new_job_schedule_type: str = "interval"
    new_job_schedule_time: str = "09:00"
    new_job_schedule_day: str = "1"
    new_job_schedule_minute: str = "0"
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
                    schedule_type = job.schedule_type or "interval"
                    if schedule_type == "interval":
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
                        job_dict["formatted_interval"] = f"Every {val} {unit}"
                    elif schedule_type == "hourly":
                        parts = (job.schedule_time or "00:00").split(":")
                        minute = parts[1] if len(parts) > 1 else "00"
                        job_dict["formatted_interval"] = f"Every hour at :{minute}"
                    elif schedule_type == "daily":
                        job_dict["formatted_interval"] = f"Daily at {job.schedule_time}"
                    elif schedule_type == "weekly":
                        days_map = {
                            0: "Monday",
                            1: "Tuesday",
                            2: "Wednesday",
                            3: "Thursday",
                            4: "Friday",
                            5: "Saturday",
                            6: "Sunday",
                        }
                        day_name = days_map.get(job.schedule_day, "Unknown Day")
                        job_dict["formatted_interval"] = (
                            f"Every {day_name} at {job.schedule_time}"
                        )
                    elif schedule_type == "monthly":
                        job_dict["formatted_interval"] = (
                            f"Monthly on day {job.schedule_day} at {job.schedule_time}"
                        )
                    else:
                        job_dict["formatted_interval"] = "Unknown Schedule"
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
                    job.next_run = datetime.now(timezone.utc)
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
        script_filename = os.path.basename(self.new_job_script_path)
        full_script_path = os.path.join(SCRIPTS_DIR, script_filename)
        if not os.path.exists(full_script_path):
            return rx.window_alert(
                f"Script '{script_filename}' not found in {SCRIPTS_DIR}.\nPlease ensure the file exists in the app/scripts directory."
            )
        interval_seconds = 0
        schedule_time = None
        schedule_day = None
        schedule_type = self.new_job_schedule_type
        try:
            if schedule_type == "interval":
                val = int(self.new_job_interval_value)
                if val < 1:
                    raise ValueError("Interval must be positive")
                multiplier = 1
                if self.new_job_interval_unit == "Minutes":
                    multiplier = 60
                elif self.new_job_interval_unit == "Hours":
                    multiplier = 3600
                elif self.new_job_interval_unit == "Days":
                    multiplier = 86400
                interval_seconds = val * multiplier
            elif schedule_type == "hourly":
                minute_val = int(self.new_job_schedule_minute)
                if not 0 <= minute_val <= 59:
                    raise ValueError("Minute must be between 0 and 59")
                schedule_time = f"00:{minute_val:02d}"
            elif schedule_type == "daily":
                schedule_time = self.new_job_schedule_time
            elif schedule_type == "weekly":
                schedule_time = self.new_job_schedule_time
                schedule_day = int(self.new_job_schedule_day)
            elif schedule_type == "monthly":
                schedule_time = self.new_job_schedule_time
                day_val = int(self.new_job_schedule_day)
                if not 1 <= day_val <= 31:
                    raise ValueError("Day of month must be between 1 and 31")
                schedule_day = day_val
        except ValueError as e:
            logging.exception(f"Invalid schedule configuration: {e}")
            return rx.window_alert(f"Invalid configuration: {e}")
        try:
            with Session(engine) as session:
                new_job = ScheduledJob(
                    name=self.new_job_name,
                    script_path=full_script_path,
                    interval_seconds=interval_seconds,
                    schedule_type=schedule_type,
                    schedule_time=schedule_time,
                    schedule_day=schedule_day,
                    is_active=True,
                    next_run=datetime.now(timezone.utc),
                )
                session.add(new_job)
                session.commit()
                session.refresh(new_job)
            self.new_job_name = ""
            self.new_job_script_path = ""
            self.new_job_interval_value = "1"
            self.new_job_interval_unit = "Hours"
            self.new_job_schedule_type = "interval"
            self.new_job_schedule_time = "09:00"
            self.new_job_schedule_day = "1"
            self.new_job_schedule_minute = "0"
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
                        job.next_run = datetime.now(timezone.utc)
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