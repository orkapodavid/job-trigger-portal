# Job Trigger Management Portal

A robust, enterprise-grade job scheduling system built with **Reflex**, featuring a real-time WebSocket architecture for instant job dispatch and monitoring.

![Python](https://img.shields.io/badge/python-3.10+-blue.svg)
![Reflex](https://img.shields.io/badge/reflex-framework-purple.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)

## 🏗️ Architecture Overview

The system uses a push-based architecture to eliminate database polling lag and simplify worker deployment:


┌─────────────────────────────────────────────────────────────────────────┐
│                         REFLEX APP (SCHEDULER)                          │
│  ┌──────────────┐    ┌───────────────┐    ┌──────────────────────────┐  │
│  │   Database   │◄──►│ Scheduler Job │◄──►│   WebSocket Handler      │  │
│  │  (SQLite)    │    │ (Background)  │    │   /ws/heartbeat          │  │
│  └──────────────┘    └───────────────┘    └────────────┬─────────────┘  │
└───────────────────────────────────────────────────────│─────────────────┘
                                                         │ WebSocket
                                                         │ (bidirectional)
┌───────────────────────────────────────────────────────│─────────────────┐
│                         WORKER (EXECUTOR)              ▼                │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │  Connects to WS → Receives job commands → Executes → Reports     │   │
│  └──────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘


### Components

1. **Reflex Web App (`app/app.py` & `app/scheduler.py`)**:
   - **Scheduler**: Runs a background loop checking the DB for due jobs.
   - **WebSocket Server**: Manages connections to workers and broadcasts real-time events.
   - **UI**: Displays live status and logs.

2. **Worker Service (`app/worker.py`)**:
   - **Stateless**: Connects via WebSocket to receive instructions.
   - **Secure**: Only executes allowed scripts.
   - **Real-time**: Pushes heartbeats and execution logs instantly.

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
You need **2 separate terminal windows**:

**Terminal 1: Web Application** (Must start first)
bash
reflex run


**Terminal 2: Worker Service**
bash
python -m app.worker


*You should see "Connected to ws://localhost:8000/ws/heartbeat" in the worker logs.*

## 📁 Project Structure


├── app/
│   ├── app.py              # Main entry point and API routes
│   ├── state.py            # UI logic and state management
│   ├── models.py           # Database schema (SQLModel)
│   ├── scheduler.py        # Background task that triggers jobs
│   ├── websocket_server.py # Hub for worker communication
│   ├── worker.py           # Standalone execution client
│   ├── job_manager.py      # Dashboard UI components
│   ├── utils.py            # Utility functions
│   └── scripts/            # Directory for executable scripts
│       └── test_job.py     # Sample test script
├── requirements.txt
├── rxconfig.py
└── README.md


## ✨ Features

- **Real-time Dashboard**: Live job status updates via WebSocket
- **Multiple Schedule Types**: Interval, Hourly, Daily, Weekly, Monthly, Manual
- **Timezone Support**: HKT (Hong Kong Time) display with UTC storage
- **Execution Logs**: Full stdout/stderr capture with status tracking
- **Worker Management**: Auto-reconnect, heartbeat monitoring
- **MS SQL Compatible**: Database schema designed for enterprise migration

## 🕒 Timezone Handling

- **Frontend**: Displays **Hong Kong Time (HKT)**
- **Backend**: Stores `next_run` in **UTC**
- **Conversion**: Handled automatically in `app/state.py`

## 🛠️ Troubleshooting

**"System Offline" in Dashboard:**
- Is `app/worker.py` running?
- Check worker logs for connection errors

**Jobs Not Running:**
- **Queued but not starting?** Check if the worker is "Online" in the dashboard
- **Execution Error?** Check the "Execution Logs" panel for STDERR output

**Worker Connection Issues:**
- Ensure WebSocket port (default 8000) is not blocked
- For remote workers: `export REFLEX_SERVER_URL="ws://<server-ip>:8000/ws/heartbeat"`

## 📜 License

MIT License - See LICENSE file for details
