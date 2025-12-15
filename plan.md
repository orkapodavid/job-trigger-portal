# Job Trigger Portal - Timezone Handling (HKT/UTC+8)

## Phase 1: Timezone Infrastructure & Worker Logic ✅
- [x] Install pytz for timezone handling
- [x] Update worker.py calculate_next_run() to convert HKT schedule times to UTC
- [x] Ensure all next_run calculations respect HKT→UTC conversion
- [x] Handle edge cases (DST not applicable for HKT, but proper UTC storage)

## Phase 2: State & UI - HKT Display and Input ✅
- [x] Update state.py to convert user input (HKT) to UTC when saving jobs
- [x] Add timezone conversion helpers for display
- [x] Update job_manager.py to display next_run and run_time in HKT
- [x] Update formatted_interval to indicate HKT times
- [x] Add HKT indicator labels to time inputs in create modal

## Phase 3: Push to GitHub ✅
- [x] Push all updated files to repository
- [x] Verify timezone handling works correctly