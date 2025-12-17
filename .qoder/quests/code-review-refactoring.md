# Code Review and Refactoring Design

## Objective

Consolidate the job scheduler codebase by organizing standalone services into a dedicated directory, removing deprecated legacy code, and establishing clear separation between the Reflex web application and independent service components.

## Background

The project has undergone migration from a WebSocket-based architecture to a database-driven coordination model. This migration left behind legacy code (WebSocket-based scheduler and worker) alongside the new database-driven services. The current structure has:

- **Active Services**: `scheduler_service.py` and `worker_service.py` (database-driven, production-ready)
- **Legacy Code**: `scheduler.py`, `worker.py`, `websocket_server.py` (deprecated, WebSocket-based)
- **Mixed Location**: All services currently reside in `app/` folder alongside Reflex web components
- **Test Confusion**: `test_scheduler.py` imports from deprecated `worker.py` instead of using `utils.py`

## Goals

1. Create clear separation between web application and standalone services
2. Remove deprecated code to eliminate confusion
3. Organize services in dedicated folder for independent execution
4. Update import statements and dependencies
5. Maintain functionality of database-driven architecture
6. Update tests to use correct modules

## Design Structure

### New Directory Organization

```
job-trigger-portal/
├── app/                          # Reflex web application only
│   ├── __init__.py
│   ├── app.py                    # Reflex app entry point
│   ├── state.py                  # UI state management
│   ├── models.py                 # Database models (shared)
│   ├── job_manager.py            # Dashboard UI components
│   ├── utils.py                  # Shared utilities (calculate_next_run)
│   └── scripts/                  # Job scripts directory
│       └── test_job.py
├── services/                     # NEW: Standalone services folder
│   ├── __init__.py
│   ├── scheduler_service.py      # Moved from app/
│   └── worker_service.py         # Moved from app/
├── tests/
│   ├── __init__.py
│   ├── test_scheduler.py         # Updated imports
│   ├── test_timezone_service.py
│   └── verify_timezone_fix.py
├── requirements.txt
├── rxconfig.py
└── README.md                     # Updated documentation
```

### Files to Remove

The following deprecated files implement the old WebSocket-based architecture and are no longer used:

1. **app/scheduler.py** - Old WebSocket-based scheduler (50 lines)
   - Replaced by: `services/scheduler_service.py`
   - Dependencies: imports `websocket_server.dispatch_job_to_worker`

2. **app/worker.py** - Old WebSocket-based worker client (180 lines)
   - Replaced by: `services/worker_service.py`
   - Note: Contains `calculate_next_run` function that was moved to `utils.py`

3. **app/websocket_server.py** - WebSocket coordination hub (208 lines)
   - Replaced by: Database polling coordination
   - Functions: worker registration, job dispatch, event broadcasting

### Files to Move

Move these files from `app/` to `services/`:

1. **scheduler_service.py** (254 lines)
   - Purpose: Database-driven job discovery and dispatch
   - Dependencies: `models`, `utils.calculate_next_run`
   - Runs independently as: `python -m services.scheduler_service`

2. **worker_service.py** (350 lines)
   - Purpose: Database-driven job execution worker
   - Dependencies: `models`
   - Runs independently as: `python -m services.worker_service`

### Import Dependencies Update

#### Current Import Structure

**scheduler_service.py imports:**
- `from app.models import ScheduledJob, JobDispatch, WorkerRegistration, JobExecutionLog, get_db_url`
- `from app.utils import calculate_next_run`

**worker_service.py imports:**
- `from app.models import WorkerRegistration, JobDispatch, JobExecutionLog, ScheduledJob, get_db_url`

**test_scheduler.py imports:**
- `from app.worker import calculate_next_run` (INCORRECT - using deprecated file)
- `from app.models import ScheduledJob`

#### Updated Import Structure

After moving services to `services/` folder:

**services/scheduler_service.py:**
- `from app.models import ScheduledJob, JobDispatch, WorkerRegistration, JobExecutionLog, get_db_url`
- `from app.utils import calculate_next_run`

**services/worker_service.py:**
- `from app.models import WorkerRegistration, JobDispatch, JobExecutionLog, ScheduledJob, get_db_url`

**tests/test_scheduler.py:**
- `from app.utils import calculate_next_run` (CORRECTED)
- `from app.models import ScheduledJob`

### Shared Module Strategy

The `app/models.py` and `app/utils.py` remain in the `app/` folder because:

1. **models.py** - Database schema shared across all components
   - Web portal reads from database
   - Scheduler service writes to database
   - Worker service reads/writes to database
   - Location: `app/models.py` (no change)

2. **utils.py** - Shared business logic
   - `calculate_next_run()` used by scheduler service and tests
   - Pure function with no UI dependencies
   - Location: `app/utils.py` (no change)

### Service Execution Model

#### Development Environment

Run services independently in separate terminals:

**Terminal 1: Scheduler Service**
```
python -m services.scheduler_service
```

**Terminal 2: Worker Service**
```
python -m services.worker_service
```

**Terminal 3: Web Portal (Optional)**
```
reflex run
```

#### Production Deployment

Each service runs as independent system service:

**Scheduler Service** - Single instance
- Discovers due jobs from database
- Creates JobDispatch records
- Monitors stuck jobs and timeouts
- Cleans up old records

**Worker Service** - Multiple instances (horizontally scalable)
- Polls for PENDING job dispatches
- Claims jobs via optimistic locking
- Executes scripts and reports results
- Sends heartbeat updates

**Web Portal** - One or more instances
- Displays job status from database
- Manages job configuration
- Views execution logs
- No direct interaction with services

## Configuration Management

### Environment Variables

**Scheduler Service Configuration:**
| Variable | Default | Description |
|----------|---------|-------------|
| `SCHEDULER_POLL_INTERVAL` | 10 | Poll for due jobs (seconds) |
| `DISPATCH_LOCK_DURATION` | 300 | Job lock duration (seconds) |
| `JOB_TIMEOUT_THRESHOLD` | 600 | Timeout for stuck jobs (seconds) |
| `MAX_RETRY_ATTEMPTS` | 3 | Maximum retry count for failed jobs |
| `CLEANUP_RETENTION_DAYS` | 30 | Retention period for old dispatches |
| `WORKER_OFFLINE_THRESHOLD` | 180 | Worker offline timeout (seconds) |

**Worker Service Configuration:**
| Variable | Default | Description |
|----------|---------|-------------|
| `WORKER_POLL_INTERVAL` | 5 | Initial poll interval (seconds) |
| `WORKER_MAX_POLL_INTERVAL` | 60 | Maximum backoff interval (seconds) |
| `WORKER_HEARTBEAT_INTERVAL` | 30 | Heartbeat update frequency (seconds) |
| `WORKER_JOB_TIMEOUT` | 600 | Job execution timeout (seconds) |

**Database Configuration (All Components):**
| Variable | Default | Description |
|----------|---------|-------------|
| `REFLEX_DB_URL` | `sqlite:///reflex.db` | Database connection string |

### Service Independence

Both services are completely independent:

- No direct communication between scheduler and worker
- No WebSocket connections required
- No shared in-memory state
- Coordination happens entirely through database tables

This enables:
- Independent deployment and scaling
- Service restart without affecting others
- Multiple worker instances for load distribution
- Fault tolerance (service failures don't cascade)

## Test Updates

### test_scheduler.py Corrections

**Current Issue:**
- Imports `calculate_next_run` from deprecated `app/worker.py`
- This creates dependency on file scheduled for removal

**Solution:**
Update import statement to use the correct module:

**Before:**
```
from app.worker import calculate_next_run
```

**After:**
```
from app.utils import calculate_next_run
```

**Impact:**
- All 30+ test cases remain unchanged
- Only the import statement needs correction
- Tests verify the same `calculate_next_run` function that services use
- No functional changes to test logic

### Test Scope

The test file validates:
- Interval scheduling (seconds, minutes, hours)
- Hourly scheduling (future/past minutes)
- Daily scheduling (UTC time handling, HKT conversion)
- Weekly scheduling (weekday calculations)
- Monthly scheduling (day of month handling)
- Edge cases (invalid formats, None values, timezone awareness)

These tests remain valuable as they verify the shared utility function used by the scheduler service.

## Migration Steps

### Step 1: Create Services Directory
Create new `services/` directory at project root with `__init__.py`

### Step 2: Move Service Files
Move files from `app/` to `services/`:
- `scheduler_service.py` → `services/scheduler_service.py`
- `worker_service.py` → `services/worker_service.py`

No import changes needed (both files already import from `app.models` and `app.utils`)

### Step 3: Update Tests
Update `tests/test_scheduler.py` import statement from deprecated `app.worker` to `app.utils`

### Step 4: Remove Deprecated Files
Delete the following files from `app/` directory:
- `scheduler.py`
- `worker.py`
- `websocket_server.py`

### Step 5: Update Documentation
Update `README.md` to reflect:
- New directory structure
- Database-driven architecture (not WebSocket-based)
- Updated service execution commands
- Three-component system (scheduler, worker, web portal)

### Step 6: Update Startup Scripts
If any startup scripts or systemd service files exist, update paths:
- Old: `python -m app.scheduler_service`
- New: `python -m services.scheduler_service`

## Verification Checklist

After refactoring, verify:

1. **Services Start Successfully**
   - [ ] `python -m services.scheduler_service` runs without errors
   - [ ] `python -m services.worker_service` runs without errors
   - [ ] Both services connect to database successfully

2. **Imports Resolve Correctly**
   - [ ] Services import from `app.models` successfully
   - [ ] Scheduler imports `calculate_next_run` from `app.utils`
   - [ ] Tests import from `app.utils` successfully

3. **Functional Testing**
   - [ ] Scheduler discovers and dispatches due jobs
   - [ ] Worker claims and executes jobs
   - [ ] Execution results saved to database
   - [ ] Web portal displays job status correctly

4. **Tests Pass**
   - [ ] `python -m pytest tests/test_scheduler.py` passes all tests
   - [ ] `python -m pytest tests/test_timezone_service.py` passes
   - [ ] No import errors in test execution

5. **Documentation Updated**
   - [ ] README.md reflects new structure
   - [ ] Architecture diagrams updated
   - [ ] Startup commands corrected

## Architecture Benefits

### Before Refactoring
- Mixed concerns (web app + services in same folder)
- Legacy code causing confusion
- Unclear which files are active vs deprecated
- Tests importing from wrong modules
- WebSocket architecture mentioned in docs but not used

### After Refactoring
- Clear separation: `app/` for web, `services/` for standalone
- Only active, production-ready code remains
- Directory structure matches deployment model
- Tests use correct shared utilities
- Documentation matches actual architecture

### System Architecture

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

### Component Isolation

Each component operates independently:

**Scheduler Service** (`services/scheduler_service.py`)
- Responsibility: Job discovery and dispatch coordination
- Database Access: Read ScheduledJob, Write JobDispatch, Read/Write WorkerRegistration
- Dependencies: `app.models`, `app.utils`
- Deployment: Single instance recommended

**Worker Service** (`services/worker_service.py`)
- Responsibility: Job execution
- Database Access: Read/Write JobDispatch, Write JobExecutionLog, Write WorkerRegistration
- Dependencies: `app.models`
- Deployment: Multiple instances supported (horizontal scaling)

**Web Portal** (`app/app.py`)
- Responsibility: User interface and job management
- Database Access: Read/Write ScheduledJob, Read JobExecutionLog, Read WorkerRegistration
- Dependencies: Reflex framework, `app.models`, `app.state`, `app.job_manager`
- Deployment: One or more instances (behind load balancer)

## Risk Assessment

### Low Risk Areas
- Creating new `services/` directory (no existing code affected)
- Moving service files (import paths remain valid)
- Updating test imports (isolated change)
- Removing deprecated files (not referenced by active code)

### Validation Required
- Ensure no production scripts directly call `app.scheduler_service` or `app.worker_service`
- Verify no systemd/supervisor configs hardcode old paths
- Confirm no deployment scripts reference deprecated files

### Rollback Strategy
If issues arise:
1. Restore `app/scheduler_service.py` and `app/worker_service.py` from backup
2. Revert test import changes
3. Keep `services/` directory for future migration attempt
4. All functionality remains intact (files were only moved, not modified)

## Future Considerations

### Additional Refactoring Opportunities
- Extract database configuration into dedicated config module
- Create shared constants module for timeout/interval values
- Add service health check endpoints
- Implement structured logging with correlation IDs

### Testing Enhancements
- Add integration tests for scheduler-worker coordination
- Create database fixture utilities for test isolation
- Add performance tests for high-volume job scheduling
- Implement end-to-end tests for complete job lifecycle

### Documentation Needs
- Add deployment guide with systemd service examples
- Create architecture decision record (ADR) documenting migration
- Document database schema migrations and upgrade path
- Add troubleshooting guide for common service issues
