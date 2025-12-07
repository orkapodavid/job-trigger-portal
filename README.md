# Job Trigger Management Portal

A production-ready, modular Python application for managing and scheduling automated job execution. Built with [Reflex](https://reflex.dev) for the web UI and a decoupled worker process for robust background job execution.

![Python](https://img.shields.io/badge/python-3.11+-blue.svg)
![Reflex](https://img.shields.io/badge/reflex-0.4+-purple.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)

## 🎯 Key Features

- **Decoupled Architecture**: Separate UI and worker processes for stability and scalability
- **Non-Blocking Execution**: Multi-threaded worker prevents long-running jobs from blocking others
- **Drift-Free Scheduling**: Jobs run at precise intervals regardless of execution time
- **Security-First**: Path traversal protection restricts script execution to approved directory
- **Real-Time Updates**: UI automatically refreshes job status and execution logs
- **Database Agnostic**: Easily migrate from SQLite to PostgreSQL, MSSQL, or other databases

## 📋 Table of Contents

- [Architecture](#architecture)
- [Quick Start](#quick-start)
- [Usage](#usage)
- [Configuration](#configuration)
- [Production Deployment](#production-deployment)
- [Database Migration](#database-migration)
- [API Reference](#api-reference)

## 🏗️ Architecture


┌─────────────────────────────────────────────────────────────┐
│                     Reflex Web UI (Frontend)                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │   Dashboard  │  │  Job Creator │  │  Log Viewer  │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└──────────────────────────┬──────────────────────────────────┘
                           │ (State Management)
                           ▼
                  ┌─────────────────┐
                  │  SQLite/MSSQL   │
                  │    Database     │
                  └─────────────────┘
                           ▲
                           │ (Direct SQL Queries)
                           │
┌──────────────────────────┴──────────────────────────────────┐
│              Worker Process (Background)                     │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │ Polling  │→ │Threading │→ │ Execute  │→ │  Log     │   │
│  │  Loop    │  │  Engine  │  │  Script  │  │ Results  │   │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘   │
└─────────────────────────────────────────────────────────────┘


### Key Design Decisions

1. **Threading Model**: Uses Python threading to execute multiple jobs concurrently without blocking the polling loop
2. **Scheduling Strategy**: Calculates next_run timestamp BEFORE execution to prevent drift
3. **Security Sandbox**: Restricts all script execution to `app/scripts/` directory
4. **Timezone Aware**: Uses UTC timestamps throughout for consistency across deployments

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- pip

### Installation

1. **Clone the repository**
   bash
   git clone https://github.com/orkapodavid/job-trigger-portal.git
   cd job-trigger-portal
   

2. **Install dependencies**
   bash
   pip install -r requirements.txt
   

3. **Initialize the database**
   bash
   python -c "from app.models import init_db; init_db()"
   

4. **Start the worker process**
   bash
   python -m app.worker
   

5. **Start the web UI** (in a separate terminal)
   bash
   reflex run
   

6. **Open your browser**
   Navigate to `http://localhost:3000`

## 📖 Usage

### Creating a Job

1. Click the **"New Job"** button
2. Fill in the form:
   - **Job Name**: Descriptive name for the job
   - **Script Path**: Filename (e.g., `my_script.py`) - file must exist in `app/scripts/`
   - **Run Every**: Interval value and unit (Seconds, Minutes, Hours, Days)
3. Click **"Create Job"**

### Managing Jobs

- **Activate/Deactivate**: Toggle the status badge to pause/resume a job
- **Run Now**: Click the play icon to execute immediately
- **Delete**: Click the trash icon to remove the job and its logs
- **View Logs**: Click any job row to see its execution history

### Adding Custom Scripts

1. Create your Python script in `app/scripts/`
2. Ensure it's executable and uses proper exit codes:
   
   # app/scripts/my_job.py
   import sys
   
   def main():
       try:
           # Your job logic here
           print("Job completed successfully")
           sys.exit(0)  # Success
       except Exception as e:
           print(f"Error: {e}", file=sys.stderr)
           sys.exit(1)  # Failure
   
   if __name__ == "__main__":
       main()
   

## ⚙️ Configuration

### Environment Variables

- `REFLEX_DB_URL`: Database connection string (default: `sqlite:///reflex.db`)

#### Example Configurations

**SQLite (default)**
bash
export REFLEX_DB_URL="sqlite:///reflex.db"


**PostgreSQL**
bash
export REFLEX_DB_URL="postgresql://user:password@localhost/jobdb"


**Microsoft SQL Server**
bash
export REFLEX_DB_URL="mssql+pyodbc://user:password@server/database?driver=ODBC+Driver+17+for+SQL+Server"


### Worker Configuration

Edit `app/worker.py` to customize:
- Poll interval (default: 5 seconds)
- Job timeout (default: 300 seconds)
- Log level

## 🚀 Production Deployment

### Running as a Service (systemd)

1. **Create worker service file** `/etc/systemd/system/job-worker.service`:
   ini
   [Unit]
   Description=Job Trigger Worker
   After=network.target

   [Service]
   Type=simple
   User=www-data
   WorkingDirectory=/path/to/job-trigger-portal
   Environment="REFLEX_DB_URL=sqlite:///reflex.db"
   ExecStart=/usr/bin/python3 -m app.worker
   Restart=always

   [Install]
   WantedBy=multi-user.target
   

2. **Create web UI service file** `/etc/systemd/system/job-ui.service`:
   ini
   [Unit]
   Description=Job Trigger Web UI
   After=network.target

   [Service]
   Type=simple
   User=www-data
   WorkingDirectory=/path/to/job-trigger-portal
   ExecStart=/usr/bin/reflex run --env production
   Restart=always

   [Install]
   WantedBy=multi-user.target
   

3. **Enable and start services**
   bash
   sudo systemctl enable job-worker job-ui
   sudo systemctl start job-worker job-ui
   

### Using Docker

dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Initialize database
RUN python -c "from app.models import init_db; init_db()"

# Run worker and UI
CMD ["sh", "-c", "python -m app.worker & reflex run --env production"]


## 🗄️ Database Migration

### SQLite → MS SQL Server

See the comprehensive guide: [`app/mssql_migration_guide.md`](app/mssql_migration_guide.md)

Key steps:
1. Install ODBC Driver 17/18 for SQL Server
2. Execute provided T-SQL schema
3. Update `REFLEX_DB_URL` environment variable
4. Restart both worker and UI processes

## 📚 API Reference

### Models

#### ScheduledJob

class ScheduledJob(SQLModel, table=True):
    id: Optional[int]
    name: str
    script_path: str
    interval_seconds: int
    is_active: bool = True
    next_run: Optional[datetime]


#### JobExecutionLog

class JobExecutionLog(SQLModel, table=True):
    id: Optional[int]
    job_id: int  # Foreign key to ScheduledJob
    run_time: datetime
    status: str  # 'SUCCESS', 'FAILURE', 'ERROR'
    log_output: str  # Captured stdout/stderr


### State Methods

- `load_jobs()`: Fetch all jobs from database
- `add_job()`: Create new scheduled job
- `toggle_job_status(job_id)`: Activate/deactivate job
- `delete_job(job_id)`: Remove job and its logs
- `run_job_now(job_id)`: Force immediate execution
- `load_logs()`: Fetch logs for selected job

## 🛡️ Security Features

1. **Path Traversal Protection**: Scripts restricted to `app/scripts/` directory
2. **Input Validation**: All user inputs validated and sanitized
3. **Subprocess Isolation**: Jobs run in isolated subprocess with timeout
4. **SQL Injection Prevention**: Parameterized queries via SQLModel/SQLAlchemy

## 🔧 Troubleshooting

### Worker not executing jobs
- Check that `app/scripts/` directory exists and contains your scripts
- Verify file permissions (scripts must be readable)
- Check worker logs for errors: `python -m app.worker`

### Jobs showing as "ERROR" status
- Ensure script path is correct (filename only, not full path)
- Check script has proper shebang or use `.py` extension
- Review log output in UI for detailed error messages

### Database locked errors (SQLite)
- SQLite has limited concurrent write capability
- Consider migrating to PostgreSQL or MSSQL for production
- Ensure only one worker process is running

## 📝 License

MIT License - see LICENSE file for details

## 🤝 Contributing

Contributions welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Submit a pull request

## 📧 Contact

For questions or support, open an issue on GitHub.

---

**Built with ❤️ using Reflex Framework**
