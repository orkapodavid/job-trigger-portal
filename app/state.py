import reflex as rx
import asyncio
import logging
import os
import pytz
from sqlmodel import Session, select, desc, create_engine, func
from typing import Optional
from datetime import datetime, timezone, timedelta
from app.models import (
    ScheduledJob,
    JobExecutionLog,
    WorkerRegistration,
    JobDispatch,
    get_db_url,
    init_db,
)
from app.utils import ensure_utc_aware

engine = create_engine(get_db_url())
SCRIPTS_DIR = os.path.join(os.getcwd(), "app", "scripts")
HKT = pytz.timezone("Asia/Hong_Kong")


def utc_to_hkt_schedule(schedule_type: str, time_str: str, day_val: Optional[int]):
    """Convert stored UTC schedule parameters to HKT for display."""
    if not time_str:
        return (time_str, day_val)
    try:
        h, m = map(int, time_str.split(":"))
        dt_utc = None
        if schedule_type == "daily":
            dt_utc = datetime(2024, 1, 1, h, m, 0, tzinfo=timezone.utc)
        elif schedule_type == "weekly":
            dt_utc = datetime(2024, 1, 1 + (day_val or 0), h, m, 0, tzinfo=timezone.utc)
        elif schedule_type == "monthly":
            dt_utc = datetime(2024, 1, day_val or 1, h, m, 0, tzinfo=timezone.utc)
        else:
            return (time_str, day_val)
        dt_hkt = dt_utc.astimezone(HKT)
        new_time = dt_hkt.strftime("%H:%M")
        new_day = None
        if schedule_type == "weekly":
            new_day = dt_hkt.weekday()
        elif schedule_type == "monthly":
            new_day = dt_hkt.day
        return (new_time, new_day)
    except Exception as e:
        logging.exception(f"Error converting UTC to HKT: {e}")
        return (time_str, day_val)


def hkt_to_utc_schedule(schedule_type: str, time_str: str, day_val: Optional[int]):
    """Convert input HKT schedule parameters to UTC for storage."""
    if not time_str:
        return (time_str, day_val)
    try:
        h, m = map(int, time_str.split(":"))
        dt_hkt = None
        if schedule_type == "daily":
            dt_hkt = HKT.localize(datetime(2024, 1, 1, h, m, 0))
        elif schedule_type == "weekly":
            dt_hkt = HKT.localize(datetime(2024, 1, 1 + (day_val or 0), h, m, 0))
        elif schedule_type == "monthly":
            dt_hkt = HKT.localize(datetime(2024, 1, day_val or 1, h, m, 0))
        else:
            return (time_str, day_val)
        dt_utc = dt_hkt.astimezone(timezone.utc)
        new_time = dt_utc.strftime("%H:%M")
        new_day = None
        if schedule_type == "weekly":
            new_day = dt_utc.weekday()
        elif schedule_type == "monthly":
            new_day = dt_utc.day
        return (new_time, new_day)
    except Exception as e:
        logging.exception(f"Error converting HKT to UTC: {e}")
        return (time_str, day_val)


class State(rx.State):
    """
    Main state for the Job Trigger Portal.
    Manages job CRUD, log viewing, and periodic updates.
    """

    jobs: list[dict] = []
    logs: list[JobExecutionLog] = []
    running_job_ids: list[int] = []
    processing_job_ids: list[int] = []
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
    is_loading_logs: bool = False
    search_query: str = ""
    auto_refresh: bool = True
    log_limit: int = 50
    is_modal_open: bool = False
    worker_online: bool = False
    active_workers_count: int = 0
    last_heartbeat: str = ""
    worker_uptime: int = 0
    jobs_processed_count: int = 0
    worker_id: str = ""

    @rx.var
    def worker_status(self) -> str:
        """Computed status based on last heartbeat timestamp."""
        if not self.last_heartbeat:
            return "offline"
        try:
            last = datetime.fromisoformat(self.last_heartbeat)
            # Ensure timezone-aware for safe comparison
            last = ensure_utc_aware(last)
            now = datetime.now(timezone.utc)
            diff = (now - last).total_seconds()
            if diff > 180:
                return "offline"
            elif diff > 90:
                return "stale"
            return "online"
        except Exception as e:
            logging.exception(f"Error calculating worker status: {e}")
            return "offline"

    @rx.var
    def worker_uptime_str(self) -> str:
        """Formatted uptime string."""
        s = self.worker_uptime
        if s < 60:
            return f"{s}s"
        m = s // 60
        if m < 60:
            return f"{m}m"
        h = m // 60
        if h < 24:
            return f"{h}h {m % 60}m"
        d = h // 24
        return f"{d}d {h % 24}h"

    @rx.event
    def set_modal_open(self, value: bool):
        self.is_modal_open = value

    @rx.event
    def load_workers(self):
        """Load worker status from database."""
        try:
            with Session(engine) as session:
                workers = session.exec(select(WorkerRegistration)).all()
                
                if not workers:
                    self.worker_online = False
                    self.active_workers_count = 0
                    self.worker_id = ""
                    self.last_heartbeat = ""
                    self.worker_uptime = 0
                    self.jobs_processed_count = 0
                    return
                
                # Get the most active worker for display
                best_worker = max(workers, key=lambda w: w.jobs_processed)
                
                self.active_workers_count = len(workers)
                self.worker_online = True
                self.worker_id = best_worker.worker_id
                self.last_heartbeat = best_worker.last_heartbeat.isoformat() if best_worker.last_heartbeat else ""
                # Ensure timezone-aware before datetime arithmetic
                started_at_aware = ensure_utc_aware(best_worker.started_at)
                self.worker_uptime = int(
                    (datetime.now(timezone.utc) - started_at_aware).total_seconds()
                )
                self.jobs_processed_count = best_worker.jobs_processed
                
        except Exception as e:
            logging.exception(f"Error loading workers: {e}")
            self.worker_online = False
            self.active_workers_count = 0

    @rx.event
    def load_jobs(self):
        """Fetch all scheduled jobs from the database with dispatch status."""
        try:
            with Session(engine) as session:
                query = select(ScheduledJob)
                if self.search_query:
                    query = query.where(ScheduledJob.name.contains(self.search_query))
                query = query.order_by(ScheduledJob.id)
                results = session.exec(query).all()
                self.jobs = []
                running_ids = []
                processing_ids = []
                
                for job in results:
                    job_dict = job.model_dump()
                    schedule_type = job.schedule_type or "interval"
                    
                    # Check if job has pending/in-progress dispatches
                    pending_dispatch = session.exec(
                        select(JobDispatch)
                        .where(JobDispatch.job_id == job.id)
                        .where(JobDispatch.status.in_(["PENDING", "IN_PROGRESS"]))
                        .order_by(JobDispatch.created_at.desc())
                    ).first()
                    
                    if pending_dispatch:
                        if pending_dispatch.status == "PENDING":
                            running_ids.append(job.id)
                        elif pending_dispatch.status == "IN_PROGRESS":
                            processing_ids.append(job.id)
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
                        hkt_time, _ = utc_to_hkt_schedule(
                            "daily", job.schedule_time, None
                        )
                        job_dict["formatted_interval"] = f"Daily at {hkt_time} (HKT)"
                    elif schedule_type == "weekly":
                        hkt_time, hkt_day = utc_to_hkt_schedule(
                            "weekly", job.schedule_time, job.schedule_day
                        )
                        days_map = {
                            0: "Monday",
                            1: "Tuesday",
                            2: "Wednesday",
                            3: "Thursday",
                            4: "Friday",
                            5: "Saturday",
                            6: "Sunday",
                        }
                        day_name = days_map.get(hkt_day, "Unknown Day")
                        job_dict["formatted_interval"] = (
                            f"Every {day_name} at {hkt_time} (HKT)"
                        )
                    elif schedule_type == "monthly":
                        hkt_time, hkt_day = utc_to_hkt_schedule(
                            "monthly", job.schedule_time, job.schedule_day
                        )
                        job_dict["formatted_interval"] = (
                            f"Monthly on day {hkt_day} at {hkt_time} (HKT)"
                        )
                    elif schedule_type == "manual":
                        job_dict["formatted_interval"] = "Manual (Run on Demand)"
                    else:
                        job_dict["formatted_interval"] = "Unknown Schedule"
                    self.jobs.append(job_dict)
                self.running_job_ids = running_ids
                self.processing_job_ids = processing_ids
        except Exception as e:
            logging.exception(f"Error loading jobs: {e}")

    @rx.event
    def run_job_now(self, job_id: int):
        """Force a job to run immediately by updating its next_run time."""
        try:
            if job_id not in self.running_job_ids:
                self.running_job_ids.append(job_id)
            with Session(engine) as session:
                job = session.get(ScheduledJob, job_id)
                if job:
                    job.next_run = datetime.now(timezone.utc)
                    session.add(job)
                    session.commit()
                    self.load_jobs()
                    return rx.toast.info(
                        f"Queued '{job.name}' for immediate execution."
                    )
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
                schedule_time, _ = hkt_to_utc_schedule(
                    "daily", self.new_job_schedule_time, None
                )
            elif schedule_type == "weekly":
                schedule_time, schedule_day = hkt_to_utc_schedule(
                    "weekly", self.new_job_schedule_time, int(self.new_job_schedule_day)
                )
            elif schedule_type == "monthly":
                day_val = int(self.new_job_schedule_day)
                if not 1 <= day_val <= 31:
                    raise ValueError("Day of month must be between 1 and 31")
                schedule_time, schedule_day = hkt_to_utc_schedule(
                    "monthly", self.new_job_schedule_time, day_val
                )
            elif schedule_type == "manual":
                pass
        except ValueError as e:
            logging.exception(f"Invalid schedule configuration: {e}")
            return rx.window_alert(f"Invalid configuration: {e}")
        try:
            next_run = None if schedule_type == "manual" else datetime.now(timezone.utc)
            with Session(engine) as session:
                new_job = ScheduledJob(
                    name=self.new_job_name,
                    script_path=full_script_path,
                    interval_seconds=interval_seconds,
                    schedule_type=schedule_type,
                    schedule_time=schedule_time,
                    schedule_day=schedule_day,
                    is_active=True,
                    next_run=next_run,
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
    async def select_job(self, job_id: int):
        """Select a job to view its logs."""
        self.selected_job_id = job_id
        job = next((j for j in self.jobs if j["id"] == job_id), None)
        if job:
            self.selected_job_name = job["name"]
        self.selected_log_entry = None
        self.is_loading_logs = True
        yield
        self.load_logs()
        self.is_loading_logs = False

    @rx.event
    async def refresh_logs(self):
        """Explicitly refresh the logs for the selected job."""
        if self.selected_job_id:
            self.is_loading_logs = True
            yield
            self.load_logs()
            self.is_loading_logs = False

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
        """
        Initial load and periodic refresh.
        Loads jobs and worker status from database.
        """
        init_db()
        async with self:
            self.load_jobs()
            self.load_workers()
        
        # Periodic refresh loop (every 5 seconds)
        while True:
            await asyncio.sleep(5)
            async with self:
                if self.auto_refresh:
                    self.load_jobs()
                    self.load_workers()
                    if self.selected_job_id:
                        self.load_logs()
