# Database-Driven Job Scheduler Architecture - Redesign for Horizontal Scalability

## Executive Summary

This design proposes a fundamental architecture shift from WebSocket-based job distribution to a database-driven coordination model. The new architecture decouples all three components (Web Portal, Scheduler, Workers) to enable independent scaling, eliminate WebSocket complexity, and provide a more robust foundation for production deployments.

## Problem Statement

### Current Architecture Issues

The existing WebSocket-based architecture has several critical limitations:

1. **Tight Coupling**: Scheduler embedded in Reflex web app creates event loop conflicts and prevents independent scaling
2. **WebSocket Complexity**: Real-time communication adds failure points, requires connection state management, and complicates deployment
3. **Single Point of Failure**: Scheduler runs as part of web app, so web app restarts disrupt job scheduling
4. **Horizontal Scaling Limitations**: Cannot scale workers independently without complex WebSocket connection pooling
5. **Observability Gaps**: Worker state managed in-memory makes debugging and monitoring difficult

### Observed Symptoms (Current System)

- Manual jobs remain stuck in "Queued" state indefinitely
- Scheduled jobs update their next_run timestamp but never execute
- Worker shows 0 processed jobs despite WebSocket connection being active
- Event loop separation between Reflex and FastAPI prevents scheduler from accessing WebSocket connections
- No clear separation of concerns between scheduling and execution

## Proposed Architecture: Database as Coordination Hub

### Architectural Principles

1. **Database as Single Source of Truth**: All state stored in database, no in-memory coordination
2. **Component Independence**: Each component (Portal, Scheduler, Workers) runs as separate process
3. **Polling-Based Coordination**: Components poll database for state changes instead of push-based messaging
4. **Stateless Workers**: Workers maintain no internal state, only execute and report via database
5. **Horizontal Scalability**: All components can scale independently without coordination overhead

### System Components

#### Component 1: Reflex Web Portal (Management UI)

**Responsibility**: Provide user interface for job management and monitoring

**Capabilities**:
- Create, edit, delete scheduled jobs
- View job execution history and logs
- Monitor worker health and activity
- Trigger manual job executions
- Display real-time system metrics

**Technology Stack**:
- Reflex for frontend and backend
- SQLModel for database interactions
- No WebSocket server required
- No scheduler logic

**Database Interactions**:
- Read/Write: ScheduledJob table (CRUD operations)
- Read: JobExecutionLog table (view logs)
- Read: WorkerRegistration table (monitor workers)
- Read: JobDispatch table (view dispatch status)

**Scaling Characteristics**:
- Stateless web application
- Can run multiple instances behind load balancer
- No coordination between instances required
- Database handles concurrent access

#### Component 2: Job Scheduler (Independent Service)

**Responsibility**: Discover due jobs and create dispatch assignments for workers

**Core Logic**:
1. Poll database every N seconds for due jobs
2. For each due job, create JobDispatch record with status "PENDING"
3. Update ScheduledJob next_run to prevent duplicate dispatch
4. Monitor JobDispatch table for stuck jobs and handle retries
5. Clean up completed dispatch records older than retention period

**Technology Stack**:
- Standalone Python service
- SQLModel for database interactions
- No Reflex dependency
- No WebSocket dependency
- Simple event loop with database polling

**Database Interactions**:
- Read: ScheduledJob table (find due jobs)
- Write: JobDispatch table (create dispatch assignments)
- Update: ScheduledJob table (update next_run after dispatch)
- Read/Update: WorkerRegistration table (check worker availability)

**Scaling Characteristics**:
- Can run single instance (active) with hot standby for high availability
- Leader election via database lock mechanism
- No horizontal scaling needed (database is bottleneck, not scheduler)
- If needed, can shard by job_id ranges for massive scale

#### Component 3: Worker Service (Execution Engine)

**Responsibility**: Execute jobs and report results

**Core Logic**:
1. Register worker in WorkerRegistration table on startup
2. Poll JobDispatch table for PENDING jobs
3. Claim job by updating status to IN_PROGRESS with worker_id and timestamp
4. Execute script and capture output
5. Update JobDispatch status to COMPLETED or FAILED
6. Create JobExecutionLog record with results
7. Send heartbeat updates to WorkerRegistration table
8. Handle graceful shutdown by releasing claimed jobs

**Technology Stack**:
- Standalone Python service
- SQLModel for database interactions
- subprocess for script execution
- No Reflex dependency
- No WebSocket dependency

**Database Interactions**:
- Write: WorkerRegistration table (registration and heartbeat)
- Read/Update: JobDispatch table (claim and update jobs)
- Write: JobExecutionLog table (execution results)

**Scaling Characteristics**:
- Fully horizontally scalable
- Each worker independently polls for jobs
- Database transaction ensures only one worker claims each job
- No coordination between workers required
- Can add/remove workers dynamically

### Data Model Extensions

#### New Table: WorkerRegistration

**Purpose**: Track registered workers and their health status

| Column | Type | Description |
|--------|------|-------------|
| worker_id | VARCHAR(50) PRIMARY KEY | Unique worker identifier |
| hostname | VARCHAR(255) | Server hostname |
| platform | VARCHAR(50) | OS platform (Windows/Linux/Mac) |
| started_at | DATETIME | Worker process start time |
| last_heartbeat | DATETIME | Last heartbeat timestamp |
| status | VARCHAR(20) | IDLE, BUSY, OFFLINE |
| jobs_processed | INT | Total jobs processed by this worker |
| current_job_id | INT NULL | Job currently being executed |
| process_id | INT | OS process ID |

**Indexes**:
- PRIMARY KEY on worker_id
- INDEX on last_heartbeat (for stale worker cleanup)
- INDEX on status (for available worker queries)

**Cleanup Logic**: Scheduler marks workers as OFFLINE if last_heartbeat > 3 minutes old

#### New Table: JobDispatch

**Purpose**: Queue of job assignments and execution tracking

| Column | Type | Description |
|--------|------|-------------|
| id | INT PRIMARY KEY AUTO_INCREMENT | Unique dispatch ID |
| job_id | INT NOT NULL | Foreign key to ScheduledJob |
| created_at | DATETIME | When dispatch was created |
| claimed_at | DATETIME NULL | When worker claimed job |
| completed_at | DATETIME NULL | When execution finished |
| status | VARCHAR(20) | PENDING, IN_PROGRESS, COMPLETED, FAILED, TIMEOUT |
| worker_id | VARCHAR(50) NULL | Worker that claimed/executed job |
| retry_count | INT DEFAULT 0 | Number of retry attempts |
| error_message | TEXT NULL | Error details if failed |

**Indexes**:
- PRIMARY KEY on id
- INDEX on (status, created_at) for worker polling
- INDEX on job_id for job history
- INDEX on worker_id for worker activity
- INDEX on claimed_at for timeout detection

**Status Transitions**:
- PENDING → IN_PROGRESS (worker claims job)
- IN_PROGRESS → COMPLETED (successful execution)
- IN_PROGRESS → FAILED (execution error)
- IN_PROGRESS → TIMEOUT (worker died, no heartbeat)
- FAILED → PENDING (retry after delay)

#### Modified Table: ScheduledJob

**Changes**: Add locking mechanism to prevent duplicate dispatch

| New Column | Type | Description |
|------------|------|-------------|
| last_dispatched_at | DATETIME NULL | Timestamp of last dispatch creation |
| dispatch_lock_until | DATETIME NULL | Prevent redispatch until this time |

**Purpose**: 
- last_dispatched_at: Audit trail of when job was queued
- dispatch_lock_until: Prevent scheduler from creating duplicate dispatches if job execution takes longer than interval

### Message Flow Diagrams

#### Flow 1: Scheduled Job Execution

```
Scheduler (every 10s)          Database                Worker Pool (every 5s)
      │                          │                              │
      │──── Query due jobs ─────→│                              │
      │←─── Return job #123 ─────│                              │
      │                          │                              │
      │── Create JobDispatch ───→│                              │
      │    (PENDING, job_id=123) │                              │
      │                          │                              │
      │── Update ScheduledJob ──→│                              │
      │    (next_run += interval)│                              │
      │                          │                              │
      │                          │←──── Query PENDING jobs ────│
      │                          │      WHERE status=PENDING   │
      │                          │                              │
      │                          │───── Return dispatch #456 ──→│
      │                          │                              │
      │                          │←──── Claim job (UPDATE) ────│
      │                          │      SET status=IN_PROGRESS │
      │                          │      SET worker_id=worker-A │
      │                          │                              │
      │                          │                              │ Execute
      │                          │                              │ script
      │                          │                              │  ↓
      │                          │←──── Report result ─────────│
      │                          │      UPDATE status=COMPLETED│
      │                          │      INSERT JobExecutionLog │
```

#### Flow 2: Manual Job Trigger

```
Web Portal                  Database                Scheduler
    │                          │                         │
    │── Click "Run Now" ──────│                         │
    │                          │                         │
    │── UPDATE ScheduledJob ──→│                         │
    │    SET next_run=NOW()    │                         │
    │                          │                         │
    │                          │←──── Poll for due jobs ─│
    │                          │                         │
    │                          │───── Return job ───────→│
    │                          │                         │
    │                          │←──── Create dispatch ───│
    │                          │                         │
    │                          │                         │
    │                          │          [Worker claims and executes]
    │                          │                         │
    │                          │                         │
UI Refresh (polling)         │                         │
    │                          │                         │
    │── Query execution logs ─→│                         │
    │←─── Return logs ─────────│                         │
    │                          │                         │
    │  Display result          │                         │
```

#### Flow 3: Worker Heartbeat and Health

```
Worker Process              Database                Scheduler/Web Portal
      │                        │                              │
      │──── Register ─────────→│                              │
      │     INSERT worker_id   │                              │
      │     status=IDLE        │                              │
      │                        │                              │
   [Every 30s]                 │                              │
      │                        │                              │
      │──── Heartbeat ────────→│                              │
      │     UPDATE last_hb     │                              │
      │     status=IDLE/BUSY   │                              │
      │                        │                              │
      │                        │                              │
      │                        │                              │
   [Worker crashes]            │                              │
      X                        │                              │
                               │                              │
                               │←──── Cleanup query (Scheduler)│
                               │      DELETE workers WHERE   │
                               │      last_hb < NOW() - 3min │
                               │                              │
                               │                              │
                               │←──── Monitor query (Portal) ─│
                               │      SELECT * FROM workers  │
                               │                              │
                               │───── Return worker list ────→│
```

### Concurrency and Race Condition Handling

#### Challenge 1: Multiple Schedulers Creating Duplicate Dispatches

**Scenario**: Two scheduler instances running simultaneously both detect the same due job

**Solution**: Database-level locking with dispatch_lock_until

**Implementation**:
```
Scheduler queries:
SELECT * FROM scheduled_jobs 
WHERE is_active = TRUE 
  AND next_run <= NOW()
  AND (dispatch_lock_until IS NULL OR dispatch_lock_until < NOW())
FOR UPDATE SKIP LOCKED

For each job:
  BEGIN TRANSACTION
    INSERT INTO job_dispatch (job_id, status) VALUES (job.id, 'PENDING')
    UPDATE scheduled_jobs 
    SET next_run = calculate_next_run(...),
        last_dispatched_at = NOW(),
        dispatch_lock_until = NOW() + INTERVAL 5 MINUTE
    WHERE id = job.id
  COMMIT
```

**Result**: Only one scheduler can lock and process each job, SKIP LOCKED prevents blocking

#### Challenge 2: Multiple Workers Claiming Same Job

**Scenario**: Two workers query JobDispatch table simultaneously and see same PENDING job

**Solution**: Optimistic locking with UPDATE WHERE clause

**Implementation**:
```
Worker queries:
SELECT id FROM job_dispatch 
WHERE status = 'PENDING' 
ORDER BY created_at ASC 
LIMIT 1

Worker attempts claim:
UPDATE job_dispatch 
SET status = 'IN_PROGRESS',
    worker_id = 'worker-abc',
    claimed_at = NOW()
WHERE id = {dispatch_id}
  AND status = 'PENDING'  -- Critical: only claim if still PENDING

Check affected rows:
IF affected_rows == 1:
  Job claimed successfully, proceed with execution
ELSE:
  Another worker claimed it, query for next job
```

**Result**: Database ensures only one UPDATE succeeds, other workers get 0 affected rows

#### Challenge 3: Worker Dies Mid-Execution

**Scenario**: Worker claims job, starts execution, then crashes before reporting result

**Solution**: Timeout monitoring by scheduler

**Implementation**:
```
Scheduler cleanup task (every 60s):
SELECT * FROM job_dispatch
WHERE status = 'IN_PROGRESS'
  AND claimed_at < NOW() - INTERVAL 10 MINUTE

For each stuck job:
  - Look up worker_id in WorkerRegistration
  - If worker is OFFLINE (no recent heartbeat):
      UPDATE job_dispatch SET status = 'TIMEOUT'
      INSERT INTO JobExecutionLog (status='TIMEOUT', log='Worker died during execution')
      If retry_count < 3:
        CREATE new JobDispatch with retry_count++
```

**Result**: Jobs don't get lost if workers crash, automatic retry with backoff

#### Challenge 4: Database Connection Pool Exhaustion

**Scenario**: 100 workers all polling database every 5 seconds creates 20 queries/second

**Solution**: Exponential backoff when no jobs available

**Implementation**:
```
Worker polling logic:
poll_interval = 5  # seconds
max_poll_interval = 60  # seconds

while running:
  job = query_and_claim_job()
  
  if job is not None:
    execute_job(job)
    poll_interval = 5  # Reset to fast polling after job
  else:
    sleep(poll_interval)
    poll_interval = min(poll_interval * 1.5, max_poll_interval)  # Exponential backoff
```

**Result**: Workers automatically reduce polling frequency when idle, saving database connections

### Performance Characteristics

#### Latency Analysis

| Event | Expected Latency | Components Involved |
|-------|------------------|---------------------|
| User clicks "Run Now" | < 100ms | Portal → Database UPDATE |
| Scheduler detects due job | 0-10s (poll interval) | Database ← Scheduler query |
| Worker claims job | 0-5s (poll interval) | Database ← Worker query |
| Job execution starts | < 1s after claim | Worker subprocess spawn |
| Result appears in UI | 0-5s after completion | Database ← Portal query (polling) |

**Total latency (manual job)**: 5-16 seconds from button click to execution start

**Breakdown**:
- Portal update: <0.1s
- Scheduler detection: 0-10s (average 5s)
- Worker claim: 0-5s (average 2.5s)
- Execution start: <1s

**Optimization**: Can reduce scheduler poll interval to 5s and worker poll to 2s for 2-8s total latency

#### Throughput Capacity

**Scheduler Throughput**:
- Database query: ~10ms
- Dispatch creation: ~5ms per job
- **Theoretical max**: ~60 jobs/second with 10s poll interval = 600 jobs per cycle
- **Practical limit**: 100-200 jobs per poll cycle to keep query time reasonable

**Worker Throughput**:
- Job claim: ~10ms
- Result recording: ~15ms
- **Per-worker overhead**: ~25ms
- **With 100 workers**: Can handle 4,000 short jobs/second (ignoring actual execution time)

**Database Throughput** (primary bottleneck):
- SQLite: 1,000-10,000 INSERT/UPDATE per second (limited, not recommended for >10 workers)
- PostgreSQL: 10,000-50,000 transactions per second (recommended for production)
- MS SQL Server: 20,000-100,000 transactions per second (enterprise deployments)

#### Scalability Limits

| Component | Scaling Model | Practical Limit | Bottleneck |
|-----------|---------------|-----------------|------------|
| Web Portal | Horizontal | Unlimited | Database connection pool |
| Scheduler | Active/Standby | 1 active + N standby | Database lock contention |
| Workers | Horizontal | 1,000+ | Database connection pool |
| Database | Vertical + Replication | 100,000 jobs/day | Disk I/O for logs |

**Recommendation for massive scale (>10,000 jobs/day)**:
- Use PostgreSQL or MS SQL Server (not SQLite)
- Configure connection pooling (max 100 connections total)
- Partition JobExecutionLog table by date
- Archive old logs to separate database/storage
- Use read replicas for Web Portal queries

## Root Cause Analysis (Current System Issues)

### Issue 1: Scheduler Event Loop Configuration

**Location:** `app/app.py` line 18-20

**Current Implementation:**
```
@api.on_event("startup")
async def startup_event():
    asyncio.create_task(run_scheduler())
```

**Problem:** The FastAPI startup event creates a task in the FastAPI event loop, but Reflex runs its own separate event loop for the web application. The scheduler task may be created but not properly executing or may be executing in an isolated loop without access to the WebSocket connections managed by the main Reflex loop.

**Evidence:**
- Scheduler logs show "Scheduler background task started" (indicating task creation succeeds)
- No subsequent logs showing "Job ... is due. Attempting dispatch..." (indicating the loop is not executing or not finding jobs)
- Worker processes 0 jobs despite being connected

### Issue 2: Worker Status Mismatch in get_available_worker()

**Location:** `app/websocket_server.py` line 73-75

**Current Logic:**
```
for wid, data in connected_workers.items():
    if data.get("status") == "idle" and wid in connected_sockets:
        return wid
```

**Problem:** The worker sends `"status": "idle"` in heartbeat messages (line 109 of worker.py), but the condition checks for exact string match. However, the connected_workers dictionary is updated with the entire heartbeat message data, which includes the status field. The real issue is that even if this check fails, the fallback loop (lines 76-78) should return any connected worker.

**Critical Insight:** The function should be working, but we need to verify the actual data structure in connected_workers to confirm the worker is being found.

### Issue 3: Database Query Timing Precision

**Location:** `app/scheduler.py` line 21-27

**Current Query:**
```
now = datetime.now(timezone.utc)
query = (
    select(ScheduledJob)
    .where(ScheduledJob.is_active == True)
    .where(ScheduledJob.next_run != None)
    .where(ScheduledJob.next_run <= now)
)
```

**Potential Problem:** If next_run is set to exactly `now` or microseconds in the future, there's a race condition where the scheduler poll (every 10 seconds) might miss jobs that were queued between polls. However, this should only delay execution by up to 10 seconds, not prevent it entirely.

### Issue 4: Manual Job Lifecycle Management

**Location:** `app/state.py` line 220-237 and `app/scheduler.py` line 36-37

**Flow Analysis:**
1. User clicks "Run Now" on manual job
2. `run_job_now()` sets `next_run = datetime.now(timezone.utc)` (line 228)
3. Job is committed to database
4. Scheduler should detect job with next_run <= now
5. After dispatch, scheduler calls `calculate_next_run(job)` (line 36 of scheduler.py)
6. For manual jobs, `calculate_next_run()` returns None (line 15-16 of utils.py)
7. Job's next_run is set to None, preventing re-execution

**Problem:** The flow is correct, but if the scheduler is not running or not finding the worker, the job remains in "queued" state forever.

## Investigation Requirements

### Verification Needed

1. **Scheduler Execution Verification**
   - Add comprehensive logging to scheduler loop to confirm:
     - Loop iterations are occurring every 10 seconds
     - Database queries are executing
     - Jobs are being found by the query
     - dispatch_job_to_worker is being called

2. **Worker Discovery Verification**
   - Log the contents of connected_workers dictionary
   - Log the result of get_available_worker() calls
   - Verify worker_id matching between heartbeat messages and dispatch attempts

3. **WebSocket Message Flow**
   - Confirm execute_job messages are being sent to worker
   - Verify worker is receiving and processing execute_job messages
   - Check for any WebSocket send failures

## Proposed Solutions

### Solution 1: Enhanced Scheduler Logging (Diagnostic)

**Objective:** Identify which component in the dispatch chain is failing

**Changes Required:**

| File | Location | Modification |
|------|----------|--------------|
| `app/scheduler.py` | Line 19 (after while True) | Add loop iteration counter and timestamp logging |
| `app/scheduler.py` | Line 29 (after query) | Log count of jobs found and their details |
| `app/scheduler.py` | Line 34 (before dispatch call) | Log worker availability check result |
| `app/websocket_server.py` | Line 84 (start of dispatch function) | Log connected_workers state and selected worker_id |
| `app/websocket_server.py` | Line 89 (after send) | Log WebSocket send success/failure |

**Implementation Strategy:**
- Use structured logging with distinct log levels (DEBUG for iterations, INFO for actions, WARNING for failures)
- Include job_id, worker_id, and timestamps in all log messages
- Log the full state of connected_workers when no worker is available

### Solution 2: Scheduler Event Loop Fix

**Objective:** Ensure scheduler runs in the correct event loop with access to WebSocket connections

**Approach A: Reflex Background Task**

Use Reflex's built-in background task mechanism instead of FastAPI startup event.

**Changes:**
- Remove scheduler startup from `api.on_event("startup")`
- Create a State event handler with `@rx.event(background=True)`
- Start scheduler task from State.on_load()

**Rationale:** This ensures the scheduler runs in the same event loop as the Reflex application and has access to all WebSocket connections managed by the app.

**Approach B: Shared Event Loop Reference**

Keep current FastAPI startup approach but ensure shared event loop.

**Changes:**
- Store a reference to the main event loop when app starts
- Pass event loop reference to scheduler
- Ensure dispatch_job_to_worker uses the correct loop for async operations

**Recommendation:** Approach A is preferred as it's more idiomatic to Reflex and reduces coupling between FastAPI and Reflex event loops.

### Solution 3: Worker Selection Robustness

**Objective:** Ensure worker discovery works reliably regardless of heartbeat message structure

**Changes:**

| Current Logic | Improved Logic |
|--------------|----------------|
| Check status == "idle" | Check status == "idle" OR status is None OR status not present |
| Fall back to any worker in connected_workers | Add logging before fallback, verify worker is in connected_sockets |
| Return None if no workers | Log detailed diagnostic information about why no worker was found |

**Implementation:**
```
def get_available_worker() -> Optional[str]:
    if not connected_workers:
        logger.warning("No workers registered")
        return None
    
    # First pass: prefer idle workers
    for wid, data in connected_workers.items():
        if wid in connected_sockets:
            status = data.get("status", "unknown")
            if status == "idle":
                logger.debug(f"Selected idle worker: {wid}")
                return wid
    
    # Second pass: any connected worker
    for wid in connected_workers:
        if wid in connected_sockets:
            logger.info(f"Selected busy worker: {wid}")
            return wid
    
    logger.error(f"No available workers. Registered: {list(connected_workers.keys())}, Connected: {list(connected_sockets.keys())}")
    return None
```

### Solution 4: Manual Job Queue Status Management

**Objective:** Provide clear feedback when jobs are queued but not dispatching

**Changes:**

1. **Add dispatch attempt tracking**
   - Add field to ScheduledJob or JobExecutionLog to track dispatch attempts
   - Update UI to show "Dispatch failed - No workers" vs "Queued - Pending dispatch"

2. **Retry mechanism for failed dispatches**
   - If dispatch fails (returns False), don't clear next_run
   - Add backoff logic to prevent continuous retry spam
   - Log each retry attempt with reason for failure

3. **Manual job timeout**
   - After N failed dispatch attempts or X minutes in queue, create a JobExecutionLog with status "DISPATCH_FAILED"
   - Clear next_run to remove from queue
   - Send UI notification about dispatch failure

### Solution 5: Scheduler Query Optimization

**Objective:** Ensure all due jobs are found reliably

**Changes:**

1. **Add query result logging**
   ```
   due_jobs = session.exec(query).all()
   logger.info(f"Scheduler poll: Found {len(due_jobs)} due jobs at {now.isoformat()}")
   for job in due_jobs:
       logger.debug(f"  - Job {job.id} ({job.name}): next_run={job.next_run.isoformat()}")
   ```

2. **Add safety margin to query**
   ```
   # Find jobs due in the next 15 seconds (1.5x poll interval)
   query = (
       select(ScheduledJob)
       .where(ScheduledJob.is_active == True)
       .where(ScheduledJob.next_run != None)
       .where(ScheduledJob.next_run <= now + timedelta(seconds=15))
   )
   ```

3. **Add deduplication tracking**
   - Maintain in-memory set of recently dispatched job IDs
   - Skip jobs dispatched within last 30 seconds to prevent double-dispatch
   - Clear tracking set periodically

## Testing Strategy

### Test Case 1: Single Manual Job Execution

**Objective:** Verify basic dispatch mechanism works

**Steps:**
1. Ensure worker is connected and idle
2. Create manual job via UI
3. Click "Run Now"
4. Verify job appears in scheduler logs within 10 seconds
5. Verify dispatch_job_to_worker is called
6. Verify execute_job message sent to worker
7. Verify worker executes script
8. Verify job_result message received by server
9. Verify UI shows execution log

**Expected Results:**
- Job executes within 10-15 seconds of "Run Now" click
- Execution log shows SUCCESS status
- Worker processed jobs count increments to 1

### Test Case 2: Multiple Manual Jobs Sequential

**Objective:** Verify scheduler handles job queue correctly

**Steps:**
1. Create 3 manual jobs with different scripts
2. Click "Run Now" on all 3 jobs rapidly
3. Monitor scheduler logs for job detection
4. Monitor worker logs for execution order

**Expected Results:**
- All 3 jobs detected by scheduler within 10 seconds
- All 3 jobs dispatched to worker
- Worker executes jobs sequentially (or in parallel if supported)
- All 3 execution logs appear in UI

### Test Case 3: Scheduled Interval Job

**Objective:** Verify interval-based scheduling works

**Steps:**
1. Create job with 1-minute interval
2. Wait for first execution
3. Verify job reschedules with next_run = now + 60 seconds
4. Wait for second execution
5. Verify second execution occurs at scheduled time

**Expected Results:**
- First execution occurs within 10 seconds of creation
- next_run updates to 1 minute in future
- Second execution occurs 60 seconds after first
- Pattern repeats reliably

### Test Case 4: Worker Offline Handling

**Objective:** Verify system behavior when worker disconnects

**Steps:**
1. Start worker and verify connection
2. Create and queue manual job
3. Stop worker before job dispatches
4. Verify scheduler logs "No workers available"
5. Restart worker
6. Verify queued job dispatches after worker reconnects

**Expected Results:**
- Scheduler logs warning when no workers available
- Job remains in queue (next_run not cleared)
- Job dispatches within 10 seconds of worker reconnection
- UI reflects worker status changes

### Test Case 5: Concurrent Job Execution

**Objective:** Verify worker handles multiple simultaneous jobs

**Steps:**
1. Create 5 manual jobs
2. Queue all 5 jobs within same second
3. Monitor worker logs for concurrent execution behavior
4. Verify all jobs complete

**Expected Results:**
- All 5 jobs detected by scheduler
- Worker receives all 5 execute_job messages
- Worker executes jobs (sequentially or in parallel based on design)
- All 5 execution logs recorded

## Success Metrics

| Metric | Current | Target |
|--------|---------|--------|
| Job dispatch success rate | 0% (jobs not dispatching) | 100% when worker online |
| Time from "Run Now" to execution start | N/A (infinite wait) | < 15 seconds (1.5x poll interval) |
| Scheduler loop iterations logged | 0 (no logs) | 1 per 10 seconds |
| Worker selection failures logged | 0 (silent failure) | All failures logged with diagnostic info |
| Manual job queue timeout | Never (stuck forever) | Create failure log after 5 minutes |

## Implementation Priority

### Phase 1: Diagnostics (Immediate - Required to identify root cause)

1. Add comprehensive logging to scheduler loop
2. Add logging to worker selection logic
3. Add logging to WebSocket dispatch mechanism
4. Run application and collect logs
5. Analyze logs to identify exact failure point

**Estimated Time:** 30 minutes for changes, 10 minutes for testing and log analysis

### Phase 2: Primary Fix (Based on Phase 1 findings)

**If scheduler is not running:**
- Implement Solution 2 (Scheduler Event Loop Fix)

**If scheduler is running but not finding worker:**
- Implement Solution 3 (Worker Selection Robustness)

**If worker is found but messages not sending:**
- Debug WebSocket connection and message serialization

**Estimated Time:** 1-2 hours depending on root cause

### Phase 3: Enhancements (After core functionality restored)

1. Implement manual job timeout mechanism
2. Add dispatch retry logic
3. Optimize scheduler query with safety margin
4. Add deduplication tracking
5. Improve UI feedback for dispatch failures

**Estimated Time:** 2-3 hours

### Phase 4: Comprehensive Testing

1. Execute all test cases defined above
2. Perform 24-hour stability test
3. Load test with 50+ jobs
4. Worker reconnection stress test

**Estimated Time:** 4-6 hours

## Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|------------|
| Event loop conflict between Reflex and FastAPI | High | Critical | Use Reflex-native background tasks |
| Worker status field format mismatch | Medium | High | Add robust fallback logic in worker selection |
| Database connection pooling issues | Low | Medium | Use SQLModel's connection management |
| Race conditions in job queue | Low | Low | Add deduplication tracking |
| WebSocket message serialization errors | Low | High | Add try-catch with detailed error logging |

## Open Questions

1. **Is the scheduler loop actually executing?**
   - Need to verify with iteration count logging
   - Check if FastAPI startup event is being triggered

2. **What is the exact structure of connected_workers data?**
   - Need to log the dictionary contents during dispatch attempts
   - Verify worker_id key exists and matches heartbeat sender

3. **Are there any errors being silently caught?**
   - Review all try-except blocks for overly broad exception handling
   - Add logging to all exception handlers

4. **Does the worker receive execute_job messages at all?**
   - Add logging in worker.py line 146-150 to confirm message receipt
   - Verify message type matching logic

5. **Is the database query finding the queued jobs?**
   - Log the count and details of jobs returned by the query
   - Check for timezone issues in next_run comparison

## Implementation Roadmap

### Phase 1: Database Schema Migration

**Objective**: Add new tables without disrupting existing system

**Tasks**:
1. Create WorkerRegistration table
2. Create JobDispatch table
3. Add columns to ScheduledJob (last_dispatched_at, dispatch_lock_until)
4. Create indexes for optimal query performance
5. Write migration script with rollback capability

**Database Migration SQL** (PostgreSQL/MS SQL compatible):

```
-- Create WorkerRegistration table
CREATE TABLE worker_registration (
    worker_id VARCHAR(50) PRIMARY KEY,
    hostname VARCHAR(255) NOT NULL,
    platform VARCHAR(50) NOT NULL,
    started_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_heartbeat DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR(20) NOT NULL DEFAULT 'IDLE',
    jobs_processed INT NOT NULL DEFAULT 0,
    current_job_id INT NULL,
    process_id INT NULL
)

CREATE INDEX idx_worker_last_heartbeat ON worker_registration(last_heartbeat)
CREATE INDEX idx_worker_status ON worker_registration(status)

-- Create JobDispatch table
CREATE TABLE job_dispatch (
    id INT PRIMARY KEY AUTO_INCREMENT,
    job_id INT NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    claimed_at DATETIME NULL,
    completed_at DATETIME NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'PENDING',
    worker_id VARCHAR(50) NULL,
    retry_count INT NOT NULL DEFAULT 0,
    error_message TEXT NULL,
    FOREIGN KEY (job_id) REFERENCES scheduled_jobs(id) ON DELETE CASCADE,
    FOREIGN KEY (worker_id) REFERENCES worker_registration(worker_id) ON DELETE SET NULL
)

CREATE INDEX idx_dispatch_status_created ON job_dispatch(status, created_at)
CREATE INDEX idx_dispatch_job_id ON job_dispatch(job_id)
CREATE INDEX idx_dispatch_worker_id ON job_dispatch(worker_id)
CREATE INDEX idx_dispatch_claimed_at ON job_dispatch(claimed_at)

-- Extend ScheduledJob table
ALTER TABLE scheduled_jobs 
ADD COLUMN last_dispatched_at DATETIME NULL,
ADD COLUMN dispatch_lock_until DATETIME NULL

CREATE INDEX idx_job_next_run_lock ON scheduled_jobs(next_run, dispatch_lock_until)
```

**Testing**: Create tables in test database, verify constraints and indexes work correctly

**Duration**: 2-4 hours (including testing)

### Phase 2: Standalone Scheduler Development

**Objective**: Create independent scheduler service that replaces websocket_server dispatch logic

**File Structure**:
```
app/
  scheduler_service.py       # Main scheduler daemon
  scheduler_config.py        # Configuration (poll intervals, retry limits)
  scheduler_models.py        # Extended SQLModel classes for new tables
```

**Core Implementation**:

**Scheduler Main Loop**:
- Poll database every 10 seconds for due jobs
- Create JobDispatch records for each due job
- Update ScheduledJob next_run and locks
- Monitor stuck jobs and handle timeouts
- Clean up old dispatch records

**Logging Strategy**:
- INFO: Job dispatched, job timeout detected, worker cleanup
- WARNING: Retry attempts, stuck jobs
- ERROR: Database connection failures, critical errors
- DEBUG: Poll iterations, query results

**Configuration Parameters**:

| Parameter | Default | Description |
|-----------|---------|-------------|
| SCHEDULER_POLL_INTERVAL | 10s | How often to check for due jobs |
| DISPATCH_LOCK_DURATION | 5min | Prevent duplicate dispatch |
| JOB_TIMEOUT_THRESHOLD | 10min | Mark IN_PROGRESS jobs as timeout |
| MAX_RETRY_ATTEMPTS | 3 | Maximum retries for failed jobs |
| CLEANUP_RETENTION_DAYS | 30 | Keep completed dispatches for N days |
| WORKER_OFFLINE_THRESHOLD | 3min | Mark workers offline after no heartbeat |

**Testing**: 
- Unit tests for dispatch logic
- Integration tests with test database
- Verify no duplicate dispatches under concurrent load

**Duration**: 6-8 hours

### Phase 3: Worker Service Refactoring

**Objective**: Replace WebSocket connection with database polling

**Changes to worker.py**:

**Remove**:
- All WebSocket connection code
- Heartbeat WebSocket messages
- execute_job WebSocket message handling
- Sender task queue

**Add**:
- Worker registration on startup
- Database polling for PENDING jobs
- Job claim transaction with optimistic locking
- Heartbeat database updates
- Graceful shutdown with job release

**New Worker Flow**:

```
Main Loop:
1. Register worker in WorkerRegistration table
2. Start heartbeat background task (UPDATE every 30s)
3. Enter job polling loop:
   a. Query JobDispatch for PENDING jobs
   b. Attempt to claim job (UPDATE with worker_id)
   c. If claim succeeds:
      - Update WorkerRegistration.status = BUSY
      - Execute script
      - Create JobExecutionLog
      - Update JobDispatch.status = COMPLETED
      - Update WorkerRegistration.status = IDLE
   d. If no jobs available, sleep with exponential backoff
4. On shutdown signal:
   - Release any IN_PROGRESS jobs back to PENDING
   - Delete WorkerRegistration record
```

**Configuration Parameters**:

| Parameter | Default | Description |
|-----------|---------|-------------|
| WORKER_POLL_INTERVAL | 5s | Base polling frequency |
| WORKER_MAX_POLL_INTERVAL | 60s | Maximum backoff interval |
| WORKER_HEARTBEAT_INTERVAL | 30s | Heartbeat update frequency |
| WORKER_JOB_TIMEOUT | 600s | Max execution time per job |

**Testing**:
- Test job claim race conditions (multiple workers)
- Test graceful shutdown and job release
- Test worker crash recovery
- Test heartbeat mechanism

**Duration**: 4-6 hours

### Phase 4: Web Portal Simplification

**Objective**: Remove WebSocket dependencies, simplify to pure CRUD interface

**Changes to app/state.py**:

**Remove**:
- WebSocket broadcaster subscription in on_load
- fetch_worker_status HTTP call
- Real-time event handling for job_started/job_completed

**Add**:
- Database queries for WorkerRegistration table
- Database queries for JobDispatch table
- Polling-based UI refresh (optional, can use Reflex auto-refresh)

**New State Methods**:

```
load_workers():
  Query WorkerRegistration table
  Return list of active workers with status

load_job_dispatch_status(job_id):
  Query JobDispatch for specific job
  Return dispatch history and current status

load_system_metrics():
  Aggregate queries:
  - Total active workers
  - Jobs in queue (PENDING)
  - Jobs in progress (IN_PROGRESS)
  - Jobs completed today
```

**Changes to app/app.py**:

**Remove**:
- WebSocket endpoint registration
- Scheduler startup in FastAPI event
- get_worker_status API endpoint

**Result**: Minimal Reflex app with only database interactions

**Testing**:
- Verify UI displays worker status correctly
- Test job creation and monitoring
- Verify logs display correctly

**Duration**: 3-4 hours

### Phase 5: Integration Testing and Cutover

**Objective**: Validate complete system works end-to-end

**Test Scenarios**:

1. **Single Job Execution**
   - Create manual job
   - Verify dispatch created within 10s
   - Verify worker claims and executes
   - Verify log appears in UI

2. **Concurrent Job Execution**
   - Create 10 manual jobs simultaneously
   - Verify all dispatched
   - Verify workers claim without conflicts
   - Verify all complete successfully

3. **Worker Scaling**
   - Start 1 worker, create 5 jobs
   - Add 2 more workers mid-execution
   - Verify new workers claim remaining jobs
   - Verify all jobs complete

4. **Scheduler Failover**
   - Run 2 scheduler instances
   - Verify only one creates dispatches (via dispatch_lock)
   - Kill active scheduler
   - Verify standby takes over within 10s

5. **Worker Crash Recovery**
   - Start job execution
   - Kill worker mid-execution
   - Verify scheduler detects timeout
   - Verify job retried by another worker

6. **High Load Test**
   - Create 100 interval jobs (1 minute interval)
   - Run 10 workers
   - Monitor for 1 hour
   - Verify no missed executions
   - Verify no duplicate executions

**Cutover Plan**:

1. Deploy database schema changes to production
2. Deploy new scheduler service (keep old system running)
3. Verify scheduler creates dispatches correctly
4. Deploy new worker version alongside old workers
5. Verify new workers execute jobs
6. Stop old workers
7. Deploy simplified web portal
8. Remove old WebSocket code
9. Monitor for 24 hours
10. Decommission old scheduler code

**Rollback Plan**:
- Keep old code deployable for 1 week
- Can revert to WebSocket system by redeploying old version
- New database tables don't interfere with old code
- Can run both systems in parallel during transition

**Duration**: 8-12 hours (including monitoring)

### Phase 6: Production Hardening

**Objective**: Add monitoring, alerting, and operational tooling

**Enhancements**:

1. **Metrics Collection**
   - Jobs dispatched per minute
   - Average job execution time
   - Worker utilization percentage
   - Database query latency
   - Failed job rate

2. **Alerting Rules**
   - No workers online for >5 minutes
   - Job stuck in PENDING for >30 minutes
   - Failed job rate >10%
   - Scheduler not running (no dispatches for >1 minute)

3. **Admin Tools**
   - CLI tool to manually create dispatches
   - CLI tool to reset stuck jobs
   - CLI tool to view worker status
   - Health check endpoints for load balancer

4. **Database Optimization**
   - Partition JobExecutionLog by month
   - Archive old logs to object storage
   - Add database query monitoring
   - Optimize slow queries

**Duration**: 8-16 hours

## Comparison: WebSocket vs Database-Driven Architecture

| Aspect | WebSocket (Current) | Database-Driven (Proposed) |
|--------|---------------------|---------------------------|
| **Complexity** | High (event loops, connections) | Low (simple polling) |
| **Failure Modes** | Connection drops, event loop conflicts | Database connection failures |
| **Debugging** | Difficult (in-memory state) | Easy (all state in database) |
| **Worker Scaling** | Complex (connection pooling) | Trivial (just start more workers) |
| **Scheduler Scaling** | Not possible (single instance) | Active/standby model |
| **Latency** | Low (push-based, <1s) | Medium (poll-based, 5-15s) |
| **Throughput** | Limited by event loop | Limited by database |
| **State Visibility** | Requires API calls | Direct database queries |
| **Crash Recovery** | Manual intervention | Automatic retry |
| **Deployment** | Tightly coupled components | Independent deployments |
| **Testing** | Requires mocking WebSockets | Standard database testing |

## Recommendations

### Primary Recommendation: Database-Driven Architecture

**Rationale**:
1. **Eliminates current bug**: No event loop conflicts, no WebSocket complexity
2. **Production-ready**: Used by major job systems (Celery, RQ, Sidekiq)
3. **Scalability**: Can handle 1,000+ workers without coordination overhead
4. **Simplicity**: Each component is simple, independent service
5. **Observability**: All state queryable via standard SQL

**Acceptable Tradeoffs**:
1. **Latency increase**: 1s (WebSocket push) → 5-15s (database polling)
   - Mitigation: Most jobs are scheduled (not manual), so latency doesn't matter
   - For critical manual jobs, can reduce poll intervals to 2-3s

2. **Database load**: More frequent queries
   - Mitigation: Polling with exponential backoff when idle
   - Modern databases handle 1,000s of queries/second easily

3. **No real-time UI updates**: UI polls instead of push
   - Mitigation: Reflex already supports auto-refresh
   - Most users won't notice difference with 5s UI polling

### Alternative Approach: Hybrid Model

If real-time UI updates are critical, can use database-driven coordination with optional WebSocket for UI notifications only:

- Scheduler and Workers use database (as proposed)
- Web Portal optionally connects to lightweight WebSocket for UI push updates
- WebSocket server subscribes to database change events (triggers/polling)
- If WebSocket fails, UI falls back to polling

**Benefit**: Best of both worlds (robust backend + responsive UI)

**Cost**: Additional complexity of maintaining WebSocket for UI only

**Recommendation**: Start with pure database-driven, add WebSocket later if needed

## Success Metrics

| Metric | Current | Target (Database-Driven) |
|--------|---------|---------------------------|
| Job execution success rate | 0% (broken) | 99.9% |
| Time to execute manual job | Infinite (stuck) | 5-15 seconds |
| Worker horizontal scalability | Limited (WebSocket) | 1,000+ workers |
| Scheduler high availability | Not possible | Active/standby |
| System complexity (LOC) | High (~1000 lines) | Medium (~800 lines) |
| Deployment dependencies | Tightly coupled | Fully independent |
| Mean time to recovery | Manual | Automatic (timeout retry) |
| Observability | Low (in-memory state) | High (all state in DB) |

## Conclusion

The proposed database-driven architecture solves the current WebSocket dispatch failure by eliminating the root cause (tight coupling and event loop conflicts) rather than patching symptoms. The polling-based coordination model is simpler, more reliable, and more scalable than the current WebSocket approach.

The tradeoff is slightly higher latency (5-15s vs <1s), which is acceptable for a job scheduling system where most jobs run on fixed schedules. The benefits of independent scaling, automatic crash recovery, and simplified operations far outweigh the latency cost.

This architecture is proven in production by major job queue systems (Celery with database broker, Sidekiq with Redis polling) and aligns with the user's goal of horizontally scaling workers without scaling the web portal.

**Estimated Total Implementation Time**: 35-50 hours (1-1.5 weeks for single developer)

**Risk Level**: Low (can run in parallel with existing system during transition, easy rollback)

**Confidence Level**: High (architecture pattern is well-established, addresses root cause directly)
