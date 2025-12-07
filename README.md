# Job Trigger Management Portal

A modern, production-ready job scheduling and monitoring system built with Reflex framework and Python. Manage automated tasks with real-time execution tracking and comprehensive logging.

![Job Trigger Portal](https://img.shields.io/badge/Python-3.9+-blue.svg)
![Reflex](https://img.shields.io/badge/Reflex-Latest-purple.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)

## Features

✨ **Intuitive Dashboard**
- Clean, modern UI with real-time updates
- Sortable and filterable job table
- Visual status indicators with color-coded badges
- One-click job activation/deactivation

🔄 **Flexible Scheduling**
- Support for multiple time units (seconds, minutes, hours, days)
- Human-readable interval formatting
- Instant "Run Now" functionality
- Automatic next-run calculation

📊 **Comprehensive Logging**
- Detailed execution history for each job
- Full stdout/stderr capture
- Status tracking (SUCCESS, FAILURE, ERROR, RUNNING)
- Searchable log viewer with code highlighting

🏗️ **Robust Architecture**
- Decoupled worker process for reliable execution
- SQLModel ORM with database-agnostic design
- Easy migration path to MS SQL Server, PostgreSQL, MySQL
- Graceful error handling and recovery

## Quick Start

### Prerequisites
- Python 3.9 or higher
- pip package manager

### Installation

1. Clone the repository:
bash
git clone https://github.com/orkapodavid/job-trigger-portal.git
cd job-trigger-portal


2. Install dependencies:
bash
pip install -r requirements.txt


3. Initialize the database:
bash
python -c "from app.models import init_db; init_db()"


### Running the Application

1. Start the worker process (in one terminal):
bash
python app/worker.py


2. Start the web application (in another terminal):
bash
reflex run


3. Open your browser to `http://localhost:3000`

## Usage

### Creating a Job

1. Click the "New Job" button
2. Enter job details:
   - **Job Name**: Descriptive name for the task
   - **Script Path**: Absolute path to your Python script (e.g., `/path/to/script.py`)
   - **Interval**: How often to run (e.g., "5 Hours")
3. Click "Create Job"

### Managing Jobs

- **Activate/Pause**: Toggle the play/pause button
- **Run Now**: Click the play icon to execute immediately
- **Delete**: Click the trash icon to remove the job
- **View Logs**: Click on a job row to see execution history

### Example Test Script

The repository includes a test script at `app/scripts/test_job.py`:


import sys
import datetime
import time

def main():
    print(f"[{datetime.datetime.now()}] Starting Test Job Execution...")
    print("Step 1: Initialization complete.")
    time.sleep(1)
    print("Step 2: Processing data...")
    print(f"[{datetime.datetime.now()}] Job Completed Successfully.")
    sys.exit(0)

if __name__ == "__main__":
    main()


## Database Configuration

By default, the application uses SQLite (`reflex.db`). To use a different database:

1. Set the `REFLEX_DB_URL` environment variable:

bash
# PostgreSQL
export REFLEX_DB_URL="postgresql://user:pass@localhost/dbname"

# MySQL
export REFLEX_DB_URL="mysql+pymysql://user:pass@localhost/dbname"

# MS SQL Server (see migration guide)
export REFLEX_DB_URL="mssql+pyodbc://user:pass@server/db?driver=ODBC+Driver+17+for+SQL+Server"


2. See `app/mssql_migration_guide.md` for detailed MS SQL Server setup instructions

## Project Structure


job-trigger-portal/
├── app/
│   ├── __init__.py
│   ├── app.py              # Main Reflex application
│   ├── models.py           # Database models (SQLModel)
│   ├── state.py            # Reflex state management
│   ├── job_manager.py      # UI components
│   ├── worker.py           # Background job executor
│   ├── mssql_migration_guide.md
│   └── scripts/
│       └── test_job.py     # Example job script
├── requirements.txt
├── rxconfig.py
└── README.md


## Architecture

### Decoupled Design

The system uses a **decoupled architecture** with two independent processes:

1. **Web Application (Reflex)**: Handles UI, user interactions, and database CRUD operations
2. **Worker Process**: Continuously polls for scheduled jobs and executes them

This separation ensures:
- UI remains responsive during job execution
- Jobs run reliably even if the web server restarts
- Easy horizontal scaling (multiple workers)
- Clear separation of concerns

### Data Flow


User → Web UI → Database ← Worker Process → Script Execution
                    ↓
              Execution Logs


## Advanced Configuration

### Auto-Refresh Settings

Modify in `app/state.py`:

auto_refresh: bool = True  # Enable/disable auto-refresh
log_limit: int = 50        # Maximum logs to display


### Worker Polling Interval

Modify in `app/worker.py`:

sleep_duration = 5  # Check for jobs every 5 seconds


### Script Execution Timeout

Modify in `app/worker.py`:

result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)  # 5 minutes


## Troubleshooting

### "Script not found" Error
- Ensure the script path is absolute (e.g., `/full/path/to/script.py`)
- Verify file permissions are executable
- Check that the file exists before creating the job

### Jobs Not Executing
- Verify the worker process is running (`python app/worker.py`)
- Check job is marked as "Active"
- Review worker logs for errors
- Ensure `next_run` time is in the past

### Database Connection Issues
- Check `REFLEX_DB_URL` environment variable
- Verify database server is accessible
- Ensure database user has proper permissions

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For issues, questions, or feature requests, please open an issue on GitHub.
