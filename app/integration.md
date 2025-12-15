# Job Trigger Portal - Integration Guide

This guide explains how to integrate the **Job Trigger Portal** module into an existing Reflex application or a separate Python environment. This module provides a robust, database-backed scheduling system with support for complex calendars and manual triggers.

## 1. Architecture Overview

The system consists of two decoupled components sharing a single database:
1.  **The UI Module (`job_manager.py`):** A Reflex component for managing jobs and viewing logs.
2.  **The Worker Service (`worker.py`):** A standalone Python process that polls the DB, handles scheduling logic, and executes scripts.

## 2. Integration Steps

### Step A: Dependencies & Database
1.  **Dependencies:** Ensure `requirements.txt` includes:
    txt
    sqlmodel
    reflex
    pyodbc           # For MS SQL connection
    python-dateutil  # For calendar calculations
    pytz             # For timezone handling
    
2.  **Models:** Copy `app/models.py` to your project.
3.  **Configuration:** In `rxconfig.py`, configure your database URL (MS SQL Example):
    
    config = rx.Config(
        app_name="my_main_app",
        db_url="mssql+pyodbc://user:pass@host/db_name?driver=ODBC+Driver+17+for+SQL+Server"
    )
    
4.  **Schema:** Execute the necessary SQL or run migrations to create `scheduled_jobs` and `job_execution_logs` tables.

### Step B: UI Integration
1.  Copy `app/job_manager.py`, `app/state.py`, and the `app/scripts/` directory.
2.  Import and use the dashboard component in your Reflex page:

    
    import reflex as rx
    from app.job_manager import dashboard

    def sys_admin_page() -> rx.Component:
        return rx.vstack(
            rx.heading("Task Scheduler"),
            dashboard(), # The main UI component
            width="100%",
            height="100vh"
        )
    

### Step C: Worker Setup
The worker must run continuously alongside your web app.

1.  **Run:** Execute as a module from your project root:
    bash
    python -m app.worker
    
2.  **Production:** Use a process manager like **Systemd** or **Supervisor**, or run it in a separate **Docker** container.

---

## 3. Job Scheduling & Timezones

### Supported Schedule Types
The system supports flexible scheduling. All inputs in the UI are expected in **Hong Kong Time (HKT/UTC+8)**.

| Type | Description | UI Input Example |
|------|-------------|------------------|
| **Interval** | Runs repeatedly every X units. | "Every 15 Minutes" |
| **Hourly** | Runs once per hour at a specific minute. | "Minute 30" (Runs at 9:30, 10:30...) |
| **Daily** | Runs once a day at a specific time. | "14:00" (Runs at 2pm HKT) |
| **Weekly** | Runs on a specific day of the week. | "Monday" at "09:00" |
| **Monthly** | Runs on a specific day of the month. | "Day 1" at "09:00" |
| **Manual** | Never runs automatically. Only runs when triggered. | N/A |

### ⚠️ Critical Note on Timezones
*   **Frontend (User):** All times entered and displayed are **HKT**.
*   **Backend (Storage):** All `next_run` timestamps are stored in **UTC**.
*   **Conversion:** The system automatically converts your HKT inputs (e.g., 9:00 AM) to UTC (e.g., 1:00 AM) before saving to the database.

---

## 4. Manual Jobs
Manual jobs are useful for on-demand maintenance scripts or tasks that don't need a schedule.

*   **Behavior:** When created, `next_run` is set to `NULL`.
*   **Triggering:** Clicking the "Run Now" button in the UI sets `next_run` to the current UTC timestamp.
*   **Execution:** The worker picks it up immediately, executes it, and then sets `next_run` back to `NULL` (it does not reschedule itself).

---

## 5. Debugging & Logs

The system captures **STDOUT** and **STDERR** from every execution. This is your primary tool for debugging failed scripts.

### How to Debug
1.  **UI Method:** Click on a job row in the dashboard. The right sidebar will populate with execution logs. Click a log entry to see the full output.
2.  **Database Method:** Query the `job_execution_logs` table directly if the UI is inaccessible.

#### Useful Troubleshooting Queries (T-SQL)

**Find most recent failures:**
sql
SELECT TOP 5 j.name, l.run_time, l.log_output
FROM job_execution_logs l
JOIN scheduled_jobs j ON l.job_id = j.id
WHERE l.status = 'FAILURE'
ORDER BY l.run_time DESC;


**Check what is currently queued:**
sql
SELECT name, schedule_type, next_run
FROM scheduled_jobs
WHERE is_active = 1 AND next_run IS NOT NULL
ORDER BY next_run ASC;


**Inspect specific job output (if truncated in UI):**
sql
SELECT log_output 
FROM job_execution_logs 
WHERE id = <LOG_ID>;


### Common Exit Codes
*   **SUCCESS**: Exit Code 0.
*   **FAILURE**: Non-zero exit code (e.g., 1). Check the `log_output` for Python traceback or shell errors.
*   **ERROR**: System level error (e.g., file not found, permission denied). The worker failed to even launch the subprocess.
