# Job Trigger Portal - Integration Guide

This guide explains how to integrate the **Job Trigger Portal** module into an existing Reflex application or a separate Python environment. This module provides a robust, database-backed scheduling system compatible with MS SQL Server.

## 1. Architecture Overview

The system consists of two decoupled components sharing a single database:
1.  **The UI Module (`job_manager.py`):** A Reflex component you can drop into any page to manage jobs.
2.  **The Worker Service (`worker.py`):** A standalone Python process that runs in the background, polls the DB, and executes scripts.

## 2. Integration Steps

### Step A: Database & Models
1.  Copy `app/models.py` to your project's `app/` directory.
2.  Ensure you have the necessary dependencies in your `requirements.txt`:
    ```txt
    sqlmodel
    reflex
    pyodbc  # For MS SQL connection
    python-dateutil # For calendar calculations
    ```
3.  In your main `rxconfig.py`, configure your database URL (MS SQL Example):
    ```python
    config = rx.Config(
        app_name="my_main_app",
        db_url="mssql+pyodbc://user:pass@host/db_name?driver=ODBC+Driver+17+for+SQL+Server"
    )
    ```
4.  Run migrations to create the `scheduled_jobs` and `job_execution_logs` tables.

### Step B: Adding the UI
1.  Copy `app/job_manager.py` and `app/state.py` (specifically the `JobState` logic) to your project.
2.  In your main Reflex page, import and use the dashboard component:

    ```python
    import reflex as rx
    from app.job_manager import dashboard

    def settings_page() -> rx.Component:
        return rx.vstack(
            rx.heading("System Settings"),
            # Embed the job manager here
            dashboard(),
            spacing="4",
            width="100%"
        )
    ```

### Step C: Setting up the Worker
The worker is a standalone script. It does not run inside the Reflex web server process.

1.  Copy `app/worker.py` to your project root or `scripts/` folder.
2.  **Crucial:** Ensure the worker can import your `models.py`. You may need to run it as a module:
    ```bash
    # Run from your project root
    python -m app.worker
    ```
3.  **Deployment:**
    * **Docker:** Add a separate container or entrypoint for the worker.
    * **Systemd:** Create a service file to keep `worker.py` running continuously.

## 3. Script Management Rules

* **Directory:** By default, the system looks for scripts in `app/scripts/`.
* **Security:** The system restricts execution to this folder to prevent path traversal attacks.
* **Output:** All `stdout` and `stderr` from your scripts are captured and stored in the `job_execution_logs` table.

## 4. Debugging & Database

This system is designed for MS SQL transparency. You can query the status directly:

```sql
-- Check next run times
SELECT name, schedule_type, next_run 
FROM scheduled_jobs 
WHERE is_active = 1;

-- Check failure logs
SELECT TOP 10 * FROM job_execution_logs 
WHERE status = 'FAILURE' 
ORDER BY run_time DESC;