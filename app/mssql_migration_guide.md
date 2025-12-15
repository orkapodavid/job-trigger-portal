
# Manual Migration Guide: MS SQL Server

This guide details the steps required to migrate the Job Trigger Management Portal from SQLite to Microsoft SQL Server manually. Since this project uses SQLModel (SQLAlchemy) but manual schema management is requested, you will execute T-SQL scripts directly to create the necessary tables and indexes.

## 1. Prerequisites

Before proceeding, ensure the following are installed on your system or server:

### A. ODBC Driver for SQL Server
You must install the Microsoft ODBC Driver for SQL Server (Version 17 or 18) to allow Python to communicate with the database.

- **Windows**: Download from [Microsoft's website](https://learn.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server).
- **Linux (Ubuntu/Debian)**:
  bash
  curl https://packages.microsoft.com/keys/microsoft.asc | sudo tee /etc/apt/trusted.gpg.d/microsoft.asc
  curl https://packages.microsoft.com/config/ubuntu/$(lsb_release -rs)/prod.list | sudo tee /etc/apt/sources.list.d/mssql-release.list
  sudo apt-get update
  sudo ACCEPT_EULA=Y apt-get install -y msodbcsql18
  
- **macOS**:
  bash
  brew tap microsoft/mssql-release https://github.com/Microsoft/homebrew-mssql-release
  brew update
  brew install msodbcsql18 mssql-tools18
  

### B. Python Packages
Install `pyodbc`, which is the DBAPI adapter used by SQLAlchemy for MSSQL connections.

bash
pip install pyodbc


*(Note: `pyodbc` has been added to `requirements.txt`)*

---

## 2. Database Schema Setup (T-SQL)

Execute the following T-SQL script in your SQL Server instance (using SSMS, Azure Data Studio, or `sqlcmd`) to create the database and tables. This schema exactly matches the models defined in `app/models.py`.

sql
-- 1. Create Database (if not exists)
IF NOT EXISTS (SELECT * FROM sys.databases WHERE name = 'reflex_job_db')
BEGIN
    CREATE DATABASE reflex_job_db;
END
GO

USE reflex_job_db;
GO

-- 2. Create 'scheduled_jobs' Table
IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'scheduled_jobs')
BEGIN
    CREATE TABLE scheduled_jobs (
        id INT IDENTITY(1,1) PRIMARY KEY,
        name NVARCHAR(255) NOT NULL,
        script_path NVARCHAR(1024) NOT NULL,
        interval_seconds INT NOT NULL,
        schedule_type NVARCHAR(50) NOT NULL DEFAULT 'interval',
        schedule_time NVARCHAR(10) NULL,
        schedule_day INT NULL,
        is_active BIT NOT NULL DEFAULT 1,
        next_run DATETIME2 NULL
    );
    
    -- Create index for faster lookups by name
    CREATE INDEX ix_scheduled_jobs_name ON scheduled_jobs(name);
END
GO

-- 3. Create 'job_execution_logs' Table
IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'job_execution_logs')
BEGIN
    CREATE TABLE job_execution_logs (
        id INT IDENTITY(1,1) PRIMARY KEY,
        job_id INT NOT NULL,
        run_time DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
        status NVARCHAR(50) NOT NULL,
        log_output NVARCHAR(MAX) NULL, -- 'Text' in SQLModel maps to VARCHAR(MAX) or NVARCHAR(MAX)
        
        -- Foreign Key Constraint
        CONSTRAINT FK_job_execution_logs_scheduled_jobs FOREIGN KEY (job_id) 
        REFERENCES scheduled_jobs(id) 
        ON DELETE CASCADE
    );

    -- Create index for filtering logs by job_id
    CREATE INDEX ix_job_execution_logs_job_id ON job_execution_logs(job_id);
END
GO


---

## 3. Configuration

To connect the Reflex app and the worker script to your new MSSQL database, you need to set the `REFLEX_DB_URL` environment variable.

### Connection String Format
The connection string follows this format:

mssql+pyodbc://<username>:<password>@<server>/<database>?driver=ODBC+Driver+17+for+SQL+Server

*Note: If you installed Driver 18, change the driver parameter to `ODBC+Driver+18+for+SQL+Server` and consider appending `&TrustServerCertificate=yes` if you are in a dev environment without valid SSL certificates.*

### Setting the Environment Variable

**Option A: Export in Shell (Linux/Mac)**
bash
export REFLEX_DB_URL="mssql+pyodbc://sa:YourStrong!Passw0rd@localhost/reflex_job_db?driver=ODBC+Driver+17+for+SQL+Server"


**Option B: PowerShell (Windows)**
powershell
$env:REFLEX_DB_URL = "mssql+pyodbc://sa:YourStrong!Passw0rd@localhost/reflex_job_db?driver=ODBC+Driver+17+for+SQL+Server"


**Option C: `.env` file (Recommended)**
Create a `.env` file in the project root:
env
REFLEX_DB_URL=mssql+pyodbc://sa:YourStrong!Passw0rd@localhost/reflex_job_db?driver=ODBC+Driver+17+for+SQL+Server


---

## 4. Model Alignment

The T-SQL script above was derived from `app/models.py`. If you modify the Python models in the future, you must manually update the database schema.

**Current Model Mapping:**

| Python Model (`ScheduledJob`) | SQL Type (`scheduled_jobs`) | Notes |
|-------------------------------|-----------------------------|-------|
| `id: Optional[int]`           | `INT IDENTITY(1,1)`         | Primary Key |
| `name: str`                   | `NVARCHAR(255)`             | Indexed |
| `script_path: str`            | `NVARCHAR(1024)`            | |
| `interval_seconds: int`       | `INT`                       | Used for 'interval' type |
| `schedule_type: str`          | `NVARCHAR(50)`              | e.g. daily, weekly, manual |
| `schedule_time: str`          | `NVARCHAR(10)`              | HH:MM format |
| `schedule_day: int`           | `INT`                       | 0-6 (Mon-Sun) or 1-31 |
| `is_active: bool`             | `BIT`                       | 0=False, 1=True |
| `next_run: datetime`          | `DATETIME2`                 | UTC Timestamp |

| Python Model (`JobExecutionLog`) | SQL Type (`job_execution_logs`) | Notes |
|----------------------------------|---------------------------------|-------|
| `id: Optional[int]`              | `INT IDENTITY(1,1)`             | Primary Key |
| `job_id: int`                    | `INT`                           | Foreign Key |
| `run_time: datetime`             | `DATETIME2`                     | Defaults to UTC now |
| `status: str`                    | `NVARCHAR(50)`                  | |
| `log_output: str`                | `NVARCHAR(MAX)`                 | Large text storage |

---

## 5. Verification

1.  **Start the Worker:**
    With the `REFLEX_DB_URL` set, run the worker script. It should connect without creating a `reflex.db` file (SQLite).
    bash
    python app/worker.py
    
    *Output should show: "Worker started. Polling database at mssql+pyodbc://..."*

2.  **Start the Web App:**
    bash
    reflex run
    

3.  **Test Functionality:**
    - Create a new job in the UI.
    - Verify in SSMS/SQL Client: `SELECT * FROM scheduled_jobs`.
    - Allow the job to run.
    - Verify logs in SSMS: `SELECT * FROM job_execution_logs`.

## Troubleshooting

-   **"Data source name not found"**: This usually means the ODBC driver specified in the connection string matches perfectly with the one installed. Check `/etc/odbcinst.ini` on Linux to see installed drivers.
-   **"Login failed for user"**: Check username/password.
-   **"Certificate verify failed"**: If using ODBC Driver 18, encryption is on by default. Append `&TrustServerCertificate=yes` to the connection string for local development.
