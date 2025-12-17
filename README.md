# Job Trigger Management Portal

A robust, enterprise-grade job scheduling system built with **Reflex**, featuring a **database-driven architecture** for reliable job dispatch and execution.

![Python](https://img.shields.io/badge/python-3.10+-blue.svg)
![Reflex](https://img.shields.io/badge/reflex-framework-purple.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)

## 🏗️ Architecture Overview

The system uses a database-driven coordination model with three independent components:

```
┌─────────────────────────────────────────────────────────────┐
│                         DATABASE                            │
│  ┌────────────────┐  ┌────────────────┐  ┌───────────────┐ │
│  │  ScheduledJob  │  │  JobDispatch   │  │ WorkerReg     │ │
│  │                │  │                │  │               │ │
│  │ - next_run     │  │ - status       │  │ - heartbeat   │ │
│  │ - lock_until   │  │ - worker_id    │  │ - status      │ │
│  └────────────────┘  └────────────────┘  └───────────────┘ │
└─────────────────────────────────────────────────────────────┘
         ▲  │                    ▲  │                  ▲  │
         │  │                    │  │                  │  │
         │  ▼                    │  ▼                  │  ▼
    ┌────────────┐          ┌────────────┐      ┌────────────┐
    │ SCHEDULER  │          │  WORKER 1  │      │  WORKER 2  │
    │  SERVICE   │          │  SERVICE   │      │  SERVICE   │
    │            │          │            │      │            │
    │ - Poll DB  │          │ - Claim    │      │ - Claim    │
    │ - Dispatch │          │ - Execute  │      │ - Execute  │
    │ - Monitor  │          │ - Report   │      │ - Report   │
    └────────────┘          └────────────┘      └────────────┘
         │
         │ (Read-only)
         ▼
    ┌────────────┐
    │ WEB PORTAL │
    │  (Reflex)  │
    │            │
    │ - Display  │
    │ - Configure│
    │ - Logs     │
    └────────────┘
```


### Components

1. **Scheduler Service (`services/scheduler_service.py`)**:
   - **Independent Process**: Runs as standalone service
   - **Job Discovery**: Polls database for due jobs every 10 seconds
   - **Dispatch Creation**: Creates JobDispatch records for workers
   - **Monitoring**: Detects stuck jobs, cleans up stale workers

2. **Worker Service (`services/worker_service.py`)**:
   - **Independent Process**: Runs as standalone service (horizontally scalable)
   - **Job Claiming**: Polls for PENDING dispatches using optimistic locking
   - **Execution**: Runs scripts and captures output
   - **Reporting**: Updates JobDispatch and creates execution logs

3. **Reflex Web Portal (`app/app.py`)**:
   - **UI**: Real-time dashboard displaying job status
   - **Management**: Create, edit, and configure scheduled jobs
   - **Monitoring**: View execution logs and worker status
   - **Read-Only**: Displays data from database (no direct service interaction)

## 🚀 Quick Start

### 1. Prerequisites
- Python 3.10+
- Install dependencies:

bash
pip install -r requirements.txt


### 2. Configuration
Set the database URL (defaults to SQLite):

bash
# Linux/Mac
export REFLEX_DB_URL="sqlite:///reflex.db"

# Windows PowerShell
$env:REFLEX_DB_URL = "sqlite:///reflex.db"


### 3. Running the System
You need **3 separate terminal windows**:

**Terminal 1: Scheduler Service** (Must start first)
```bash
python -m services.scheduler_service
```

**Terminal 2: Worker Service**
```bash
python -m services.worker_service
```

**Terminal 3: Web Portal** (Optional - for UI)
```bash
reflex run
```

*Note: Multiple worker instances can run simultaneously for horizontal scaling.*

## 📁 Project Structure

```
├── app/
│   ├── app.py              # Reflex web portal entry point
│   ├── state.py            # UI state management
│   ├── models.py           # Database schema (SQLModel)
│   ├── job_manager.py      # Dashboard UI components
│   ├── utils.py            # Shared utilities (calculate_next_run)
│   └── scripts/            # Directory for executable scripts
│       └── test_job.py     # Sample test script
├── services/
│   ├── scheduler_service.py # Standalone scheduler service
│   └── worker_service.py    # Standalone worker service
├── tests/
│   ├── test_scheduler.py    # Scheduler logic tests
│   └── test_timezone_service.py # Timezone conversion tests
├── requirements.txt
├── rxconfig.py
└── README.md
```

## ✨ Features

- **Real-time Dashboard**: Live job status updates from database polling
- **Multiple Schedule Types**: Interval, Hourly, Daily, Weekly, Monthly, Manual
- **Timezone Support**: HKT (Hong Kong Time) display with UTC storage
- **Execution Logs**: Full stdout/stderr capture with status tracking
- **Horizontal Scaling**: Run multiple worker instances for load distribution
- **Fault Tolerance**: Services operate independently with automatic recovery
- **Optimistic Locking**: Prevents duplicate job execution across workers

## 🕒 Timezone Handling

- **Frontend**: Displays **Hong Kong Time (HKT)**
- **Backend**: Stores `next_run` in **UTC**
- **Conversion**: Handled automatically in `app/state.py`

## 🛠️ Troubleshooting

**Jobs Not Running:**
- Ensure scheduler service is running: `python -m services.scheduler_service`
- Ensure at least one worker is running: `python -m services.worker_service`
- Check database for PENDING dispatches in `job_dispatch` table

**Worker Not Processing Jobs:**
- Check worker logs for database connection errors
- Verify worker is registered in `worker_registration` table
- Ensure script paths are absolute or relative to project root

**Scheduler Not Dispatching:**
- Check `next_run` timestamps in `scheduled_jobs` table
- Verify `is_active=TRUE` for jobs that should run
- Check scheduler logs for errors

## 📜 License

MIT License - See LICENSE file for details
