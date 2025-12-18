# Timezone-Aware Datetime Fix & End-to-End Workflow Testing

## Objective

Fix the timezone-related errors preventing the Reflex web portal from starting and validate all system workflows through comprehensive end-to-end browser testing.

## Problem Analysis

### Primary Issue: Offset-Naive vs Offset-Aware Datetime Mismatch

**Error Location**: `app/state.py`, line 174 in `load_workers()` method

**Error Message**:
```
TypeError: can't subtract offset-naive and offset-aware datetimes
ERROR:root:Error loading workers: can't subtract offset-naive and offset-aware datetimes
```

**Root Cause**:
The system attempts to calculate worker uptime by subtracting database-stored timestamps from current UTC time:
```
(datetime.now(timezone.utc) - best_worker.started_at).total_seconds()
```

While `datetime.now(timezone.utc)` returns a timezone-aware datetime, the `started_at` field retrieved from the database becomes timezone-naive due to SQLModel/SQLAlchemy's handling of datetime fields with SQLite.

### Secondary Issues

Similar timezone-awareness mismatches may exist in:
- Worker heartbeat calculations (`state.py`, line 119-121)
- Any datetime arithmetic operations involving database-retrieved timestamps
- JobDispatch completion time calculations
- Schedule time comparisons

### Database Behavior with Datetime Fields

**SQLite Limitation**: SQLite stores datetime as TEXT or INTEGER, losing timezone information
**SQLModel/SQLAlchemy**: Retrieves datetime objects as timezone-naive by default
**Application Code**: Uses timezone-aware datetime objects for current time operations

This creates an impedance mismatch requiring consistent normalization.

## Solution Strategy

### Approach: Defensive Timezone Normalization

Apply timezone-awareness normalization at the point of use rather than at storage, ensuring all datetime arithmetic operations handle both naive and aware datetime objects gracefully.

**Design Principle**: Make all datetime comparisons and arithmetic operations timezone-safe through explicit normalization helper functions.

### Normalization Helper Function

**Location**: `app/utils.py` (add new utility function)

**Function Specification**:

| Function Name | Purpose | Input | Output |
|--------------|---------|-------|--------|
| `ensure_utc_aware` | Convert any datetime to timezone-aware UTC | datetime (naive or aware) | timezone-aware datetime in UTC |

**Behavior**:
- If input is already timezone-aware: return as-is
- If input is timezone-naive: assume UTC and add timezone.utc
- If input is None: return None

**Rationale**: 
- Non-invasive: doesn't require database schema changes
- Backward compatible: works with existing naive datetime records
- Future-proof: handles both naive and aware datetime objects
- Centralized: single point of normalization logic

### Code Changes Required

#### File: `app/utils.py`

Add new utility function for datetime normalization.

**Function Definition**:
- Name: `ensure_utc_aware`
- Parameters: `dt` (Optional datetime)
- Returns: Optional timezone-aware datetime
- Logic:
  - Return None if input is None
  - Return input if already timezone-aware (has tzinfo)
  - Add UTC timezone if naive (assume UTC)

#### File: `app/state.py`

Apply normalization in the following locations:

**1. Worker Status Calculation** (line 119 in `worker_status` computed var)
- Normalize `last_heartbeat` datetime before comparison
- Current: `last = datetime.fromisoformat(self.last_heartbeat)`
- Enhanced: Apply `ensure_utc_aware()` to parsed datetime

**2. Worker Uptime Calculation** (line 174 in `load_workers()` method)
- Normalize `started_at` before subtraction
- Current: `datetime.now(timezone.utc) - best_worker.started_at`
- Enhanced: `datetime.now(timezone.utc) - ensure_utc_aware(best_worker.started_at)`

**3. Heartbeat Timestamp Storage** (line 172 in `load_workers()` method)
- Normalize `last_heartbeat` before ISO conversion
- Current: `self.last_heartbeat = best_worker.last_heartbeat.isoformat()`
- Enhanced: Add safety check for None values

#### Additional Safety Measures

**WorkerRegistration Model** (`app/models.py`):
- Verify `started_at` and `last_heartbeat` fields use `get_utc_now()` default
- Consider adding index on `last_heartbeat` for query performance

**JobDispatch Model** (`app/models.py`):
- Review datetime fields: `created_at`, `claimed_at`, `completed_at`
- Ensure all use `get_utc_now()` for consistency

## End-to-End Testing Strategy

### Testing Methodology: Browser-Driven Workflow Validation

Use Playwright MCP (Model Context Protocol) browser automation to validate all user-facing workflows in a realistic environment.

### Test Environment Setup

**Prerequisites**:
- Reflex web portal running on localhost
- Scheduler service active
- Worker service active
- Clean database state

**Browser Configuration**:
- Target: Chrome/Chromium
- Viewport: 1920x1080 (desktop)
- Network: Local (no latency simulation needed)

### Test Workflows

#### Workflow 1: Application Startup & Dashboard Load

**Objective**: Verify web portal starts without timezone errors and displays dashboard

**Steps**:
1. Navigate to `http://localhost:3000`
2. Wait for page load (check for main dashboard elements)
3. Verify no console errors related to datetime operations
4. Capture accessibility snapshot of dashboard

**Success Criteria**:
- Page loads successfully
- Worker status section visible
- Jobs list renders (empty or with existing jobs)
- No JavaScript/Python errors in console

**Expected Elements**:
- Worker status indicator
- Jobs table/grid
- "Add Job" button
- Search functionality

#### Workflow 2: Worker Status Display

**Objective**: Validate worker registration and status display without uptime calculation errors

**Steps**:
1. Ensure worker service is running
2. Refresh dashboard page
3. Locate worker status section
4. Verify uptime display format
5. Verify worker count displays correctly

**Success Criteria**:
- Worker status shows "online" (green indicator)
- Uptime string displays in readable format (e.g., "5m", "2h 15m")
- Worker count shows >= 1
- No "can't subtract offset-naive and offset-aware datetimes" error

**Data Validation**:
- Worker heartbeat timestamp is recent (within last 30 seconds)
- Jobs processed count is numeric

#### Workflow 3: Create Interval-Based Job

**Objective**: Create a simple interval job to validate job creation flow

**Steps**:
1. Click "Add Job" button
2. Fill in job form:
   - Name: "Test Interval Job"
   - Script Path: "test_job.py"
   - Schedule Type: "interval"
   - Interval Value: "1"
   - Interval Unit: "Minutes"
3. Submit form
4. Verify job appears in jobs list
5. Check job displays "Every 1 Minute"

**Success Criteria**:
- Modal opens on button click
- Form accepts all inputs
- Job creation succeeds
- Job appears in dashboard
- Schedule format displays correctly

#### Workflow 4: Create Time-Based Job (Daily Schedule)

**Objective**: Validate timezone conversion for HKT display

**Steps**:
1. Click "Add Job" button
2. Fill in job form:
   - Name: "Test Daily Job"
   - Script Path: "test_job.py"
   - Schedule Type: "daily"
   - Schedule Time: "09:00"
3. Submit form
4. Verify job displays "Daily at 09:00 (HKT)"

**Success Criteria**:
- Daily schedule time accepts HH:MM format
- Display shows correct HKT label
- No timezone conversion errors in console
- Job `next_run` stored correctly in database (as UTC)

**Database Validation**:
- Query `scheduled_jobs` table
- Verify `schedule_time` is stored in UTC (01:00 for 09:00 HKT)
- Verify `next_run` is timezone-aware UTC datetime

#### Workflow 5: Create Weekly Schedule Job

**Objective**: Test day-of-week conversion with timezone

**Steps**:
1. Create job with weekly schedule
2. Set day: "Monday"
3. Set time: "14:00"
4. Verify display: "Every Monday at 14:00 (HKT)"

**Success Criteria**:
- Day selector works correctly
- Time conversion handles day boundary crossing (if applicable)
- Display format matches expectations

#### Workflow 6: Run Job Manually

**Objective**: Trigger immediate job execution

**Steps**:
1. Locate a created job in the list
2. Click "Run Now" button
3. Observe job status change to "Pending"/"Running"
4. Wait for job completion
5. Verify status updates to "Completed"

**Success Criteria**:
- "Run Now" button triggers job dispatch
- Job status indicator changes (visual feedback)
- JobDispatch record created with status "PENDING"
- Worker claims and executes job
- Status updates to "COMPLETED" or "FAILED"

**Timing Validation**:
- Job dispatch created within 1 second
- Worker claims within 5 seconds
- Execution completes within timeout period

#### Workflow 7: View Job Execution Logs

**Objective**: Validate log viewing and timestamp display

**Steps**:
1. Click on a completed job
2. Verify logs panel displays
3. Check log entries show correct timestamps
4. Verify log output is readable
5. Click on individual log entry for details

**Success Criteria**:
- Logs load without errors
- Timestamps display in user-friendly format
- Status (SUCCESS/FAILURE) visible
- Log output content accessible

**Data Checks**:
- Run time timestamp makes sense (recent, not in future)
- Multiple log entries sorted by time (newest first)

#### Workflow 8: Toggle Job Active Status

**Objective**: Enable/disable job scheduling

**Steps**:
1. Locate an active job
2. Click toggle/disable button
3. Verify job marked as inactive
4. Confirm job stops scheduling (next_run not updated)
5. Re-enable job
6. Verify scheduling resumes

**Success Criteria**:
- Toggle action updates database
- UI reflects current status
- Inactive jobs don't create dispatches
- Re-enabled jobs schedule from current time

#### Workflow 9: Delete Job

**Objective**: Remove job and associated logs

**Steps**:
1. Select a job
2. Click delete button
3. Confirm deletion
4. Verify job removed from list
5. Check associated logs deleted

**Success Criteria**:
- Confirmation dialog appears
- Job removed from database
- Cascade delete removes logs
- UI updates immediately

#### Workflow 10: Search/Filter Jobs

**Objective**: Test job search functionality

**Steps**:
1. Enter search term in search box
2. Verify jobs list filters in real-time
3. Clear search
4. Verify all jobs display again

**Success Criteria**:
- Search filters by job name
- Filtering is case-insensitive
- Empty search shows all jobs

#### Workflow 11: Auto-Refresh Behavior

**Objective**: Validate periodic dashboard updates

**Steps**:
1. Observe dashboard with auto-refresh enabled
2. Wait for 5 seconds (refresh interval)
3. Verify jobs list updates automatically
4. Check worker status updates
5. Verify no memory leaks or performance degradation

**Success Criteria**:
- Dashboard refreshes every 5 seconds
- Updates occur smoothly without flickering
- Browser console shows no errors
- Memory usage stable over 1 minute

#### Workflow 12: Multi-Worker Scenario

**Objective**: Test concurrent worker handling

**Steps**:
1. Start second worker service instance
2. Refresh dashboard
3. Verify worker count shows 2
4. Create multiple jobs
5. Trigger simultaneous execution
6. Verify both workers claim jobs

**Success Criteria**:
- Worker count accurately reflects active workers
- Jobs distributed among workers
- No duplicate job execution (optimistic locking works)
- Status updates correctly for both workers

### Error Scenario Testing

#### Test: Worker Offline Detection

**Steps**:
1. Stop worker service
2. Wait 3 minutes (WORKER_OFFLINE_THRESHOLD)
3. Refresh dashboard
4. Verify worker status shows "offline"

**Expected**:
- Status changes from "online" to "stale" to "offline"
- Worker count decrements
- UI reflects offline state

#### Test: Stuck Job Detection

**Steps**:
1. Create job with script that hangs
2. Trigger job execution
3. Wait for timeout threshold
4. Verify scheduler marks job as TIMEOUT
5. Check retry dispatch created (if under retry limit)

**Expected**:
- Job status becomes "TIMEOUT" after threshold
- Execution log created with timeout status
- Retry dispatch appears in queue

#### Test: Invalid Script Path

**Steps**:
1. Create job with non-existent script path
2. Trigger execution
3. Verify error handling

**Expected**:
- Worker reports ERROR status
- Log contains "Script not found" message
- JobDispatch marked as FAILED

### Browser Test Implementation Approach

**Tool**: Playwright MCP browser automation

**Test Sequence**:
1. Launch browser and navigate to app
2. Execute each workflow sequentially
3. Capture screenshots at key points
4. Validate element states using accessibility snapshots
5. Check browser console for errors
6. Take final screenshot of dashboard state

**Verification Points**:
- Element visibility (buttons, tables, status indicators)
- Text content accuracy (job names, schedules, status)
- Interactive elements functionality (buttons, forms, toggles)
- No JavaScript errors in console
- No network request failures

**Data Validation**:
After each workflow, query database to verify:
- Records created/updated correctly
- Timestamps are timezone-aware
- Status transitions are logical
- Foreign key relationships maintained

## Risk Assessment & Mitigation

### Risk 1: Database Timezone Storage Inconsistency

**Risk**: Existing database records may have mix of naive/aware datetimes

**Mitigation**: 
- Helper function handles both cases transparently
- No data migration required
- Gradual normalization as records update

**Severity**: Low (handled by defensive coding)

### Risk 2: Third-Party Library Behavior Changes

**Risk**: SQLModel/SQLAlchemy timezone handling may change in future versions

**Mitigation**:
- Pin dependency versions in requirements.txt
- Document expected behavior in code comments
- Include timezone tests in test suite

**Severity**: Low (controlled by dependency locking)

### Risk 3: Multiple Timezone Support

**Risk**: Future requirement to support timezones beyond HKT

**Mitigation**:
- Current design already stores in UTC (timezone-agnostic)
- Display layer can be extended for user-selectable timezones
- Normalization helper supports any timezone

**Severity**: Low (architecture supports extension)

## Success Criteria

### Fix Validation
- Web portal starts without timezone errors
- Worker status displays correctly with uptime
- No "can't subtract offset-naive and offset-aware datetimes" errors
- All datetime arithmetic operations complete successfully

### Workflow Validation
- All 12 primary workflows complete successfully
- Error scenarios handled gracefully
- No browser console errors during testing
- Database state consistent after all operations

### Performance
- Dashboard loads in < 2 seconds
- Auto-refresh causes no UI lag
- Job execution starts within 5 seconds of dispatch
- Worker claims jobs within 1 second of availability

## Implementation Notes

### Testing Prerequisites

**Database Preparation**:
- Start with clean database or known state
- Ensure `app/scripts/test_job.py` exists and is executable
- Database URL configured correctly

**Service Startup Order**:
1. Start scheduler service first (initializes dispatch logic)
2. Start worker service second (begins job claiming)
3. Start web portal last (displays current state)

**Browser Test Setup**:
- Verify Playwright browser installed
- Configure viewport size for desktop testing
- Enable screenshot capture for debugging

### Rollback Plan

If timezone fix introduces new issues:
1. Revert changes to `app/utils.py` and `app/state.py`
2. Add explicit `.replace(tzinfo=timezone.utc)` to database retrieval points
3. Consider migration script to update existing records

### Documentation Updates

After fix is validated:
- Update TIMEZONE_FIX.md with new normalization approach
- Add troubleshooting section to README.md
- Document helper function in code comments
- Create developer guide for datetime handling best practices

## Monitoring & Validation

### Post-Deployment Checks

**Application Logs**:
- Monitor for any new timezone-related warnings
- Verify worker heartbeat updates occur regularly
- Check scheduler dispatch logs for timing accuracy

**Database Queries**:
```sql
-- Verify worker registrations have recent heartbeats
SELECT worker_id, last_heartbeat, started_at FROM worker_registration;

-- Check for stuck dispatches
SELECT * FROM job_dispatch WHERE status = 'IN_PROGRESS' AND claimed_at < datetime('now', '-10 minutes');

-- Validate scheduled jobs have future next_run times
SELECT id, name, next_run FROM scheduled_jobs WHERE is_active = 1 AND next_run IS NOT NULL;
```

**User Interface Checks**:
- Worker status indicator shows correct state
- Uptime displays without errors
- Job schedules display in HKT correctly
- Execution logs have proper timestamps

### Metrics to Track

| Metric | Expected Value | Alert Threshold |
|--------|----------------|-----------------|
| Worker uptime calculation errors | 0 | > 0 |
| Dashboard load time | < 2s | > 5s |
| Job dispatch latency | < 10s | > 60s |
| Worker claim latency | < 5s | > 30s |
| Timezone conversion errors | 0 | > 0 |
