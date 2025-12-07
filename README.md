# Job Trigger Management Portal

A modular Python codebase for managing and executing scheduled jobs, built with the Reflex framework.

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.9+-blue.svg)
![Reflex](https://img.shields.io/badge/reflex-0.8.20-purple.svg)

## 🎯 Features

- **Decoupled Architecture**: Separate frontend (Reflex) and worker (standalone Python script)
- **Job Management**: Create, activate/deactivate, and delete scheduled jobs
- **Real-time Monitoring**: Live execution logs and job status updates with auto-refresh
- **SQLite Database**: Persistent storage with potential for migration to MSSQL
- **Automated Execution**: Background worker continuously polls and executes jobs
- **Modern UI**: Clean, responsive interface with Tailwind CSS styling

## 🏗️ Architecture

### Components

1. **Frontend/State Layer** (`app/`): Reflex-based UI and state management
2. **Worker Layer** (`app/worker.py`): Independent job execution script
3. **Database Models** (`app/models.py`): SQLModel schema definitions
4. **Job Manager** (`app/job_manager.py`): Main UI components with tables, modals, and logs

### Database Schema

- **ScheduledJob**: Job configuration (name, script_path, interval_seconds, is_active, next_run)
- **JobExecutionLog**: Execution history (job_id, run_time, status, log_output)

## 📦 Installation

### Prerequisites

- Python 3.9+
- pip

### Setup

bash
# Clone the repository
git clone https://github.com/orkapodavid/job-trigger-portal.git
cd job-trigger-portal

# Install dependencies
pip install -r requirements.txt

# Initialize the database
python -c "from app.models import init_db; init_db()"


## 🚀 Usage

### Start the Web Application

bash
reflex run


The web interface will be available at `http://localhost:3000`

### Start the Worker (in a separate terminal)

bash
python app/worker.py


The worker will continuously poll for active jobs and execute them on schedule.

### Create Your First Job

1. Open the web interface at `http://localhost:3000`
2. Click the **"New Job"** button
3. Fill in the job details:
   - **Job Name**: Test Job
   - **Script Path**: `app/scripts/test_job.py`
   - **Interval**: 60 (seconds)
4. Click **"Create Job"**

The worker will automatically pick up and execute the job at the specified interval.

## 📁 Project Structure


job-trigger-portal/
├── app/
│   ├── __init__.py
│   ├── app.py              # Main Reflex application entry point
│   ├── models.py           # Database schema (ScheduledJob, JobExecutionLog)
│   ├── state.py            # Reflex state management and CRUD operations
│   ├── job_manager.py      # UI components (dashboard, tables, modals)
│   ├── worker.py           # Background job executor (decoupled script)
│   └── scripts/
│       ├── __init__.py
│       └── test_job.py     # Sample job script for testing
├── assets/                  # Static assets
├── .gitignore
├── README.md
├── rxconfig.py             # Reflex configuration
└── requirements.txt        # Python dependencies


## ⚙️ Configuration

### Database

Customize the database location by setting the `REFLEX_DB_URL` environment variable:

bash
export REFLEX_DB_URL="sqlite:///custom_path.db"
# or for PostgreSQL:
# export REFLEX_DB_URL="postgresql://user:password@localhost/dbname"


### Worker Polling Interval

The worker polls every 5 seconds by default. Modify the `sleep_duration` in `app/worker.py` to change this.

## 🔧 Development

### Implementation Phases

✅ **Phase 1: Database Models** - SQLModel definitions for ScheduledJob and JobExecutionLog  
✅ **Phase 2: Decoupled Worker** - Continuous polling, subprocess execution, atomic next_run calculation  
✅ **Phase 3: Reflex State Management** - CRUD operations, log retrieval, periodic refresh  
✅ **Phase 4-5: UI Components** - Dashboard, job table, creation modal, execution log viewer  
✅ **Phase 6: UI Verification** - Comprehensive testing of all UI states

### Creating Custom Job Scripts

Job scripts can be written in Python (.py), Bash (.sh), or any executable format:

**Python Example:**

import sys
import datetime

def main():
    print(f"[{datetime.datetime.now()}] Job started")
    # Your job logic here
    print("Job completed successfully")
    sys.exit(0)

if __name__ == "__main__":
    main()


**Bash Example:**
bash
#!/bin/bash
echo "Job started at $(date)"
# Your job logic here
echo "Job completed"
exit 0


### Testing

The included `app/scripts/test_job.py` provides a sample job that:
- Prints timestamped messages
- Simulates work with sleep delays
- Demonstrates stdout and stderr capture
- Exits cleanly with status code 0

## 🛠️ Technologies

- **[Reflex](https://reflex.dev/)**: Python web framework for reactive UIs
- **[SQLModel](https://sqlmodel.tiangolo.com/)**: SQL database ORM with Pydantic integration
- **[SQLite](https://www.sqlite.org/)**: Lightweight SQL database
- **[PyGithub](https://github.com/PyGithub/PyGithub)**: GitHub API integration
- **[Tailwind CSS](https://tailwindcss.com/)**: Utility-first CSS framework (via Reflex plugin)

## 📝 API Reference

### State Methods

- `load_jobs()`: Fetch all scheduled jobs from database
- `add_job()`: Create a new scheduled job
- `toggle_job_status(job_id)`: Activate/deactivate a job
- `delete_job(job_id)`: Delete a job and its logs
- `select_job(job_id)`: Select a job to view its execution logs
- `load_logs()`: Fetch logs for the selected job

### Worker Functions

- `run_job(job, engine)`: Execute a single job and log results
- `main()`: Main worker loop with graceful shutdown handling

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## 📄 License

This project is licensed under the MIT License.

## 👤 Author

**David OR** ([@orkapodavid](https://github.com/orkapodavid))

## 🙏 Acknowledgments

- Built with [Reflex](https://reflex.dev/)
- Designed for scalability and maintainability
- Inspired by modern job scheduling systems

---

⭐ Star this repository if you find it helpful!
