# Job Trigger Portal - Calendar-Based Scheduling Refactor

## Phase 1: Database Schema Updates ✅
- [x] Add `schedule_type` enum field (interval, hourly, daily, weekly, monthly)
- [x] Add `schedule_time` field for time-of-day (HH:MM format)
- [x] Add `schedule_day` field for day-of-week or day-of-month
- [x] Keep `interval_seconds` for backward compatibility with interval type
- [x] Update model to be MS SQL readable and human-debuggable

## Phase 2: Worker Logic - Calendar Calculations ✅
- [x] Install python-dateutil for robust date calculations
- [x] Implement `calculate_next_run()` function for each schedule type
- [x] Handle hourly: next occurrence at minute mark
- [x] Handle daily: next occurrence at specified time
- [x] Handle weekly: next occurrence on specified day and time
- [x] Handle monthly: next occurrence on specified day of month (handle edge cases)
- [x] Update job processing to use new calculation logic

## Phase 3: UI Updates - Dynamic Form Fields ✅
- [x] Add schedule type selector dropdown to create job modal
- [x] Implement conditional time picker for daily/weekly/monthly
- [x] Implement day-of-week dropdown for weekly schedule
- [x] Implement day-of-month input for monthly schedule
- [x] Update state to handle new form fields
- [x] Update job display to show human-readable schedule description
- [x] Update formatted_interval to show schedule description

## Phase 4: Push to GitHub
- [ ] Verify all changes work together
- [ ] Push updated files to https://github.com/orkapodavid/job-trigger-portal.git
- [ ] Confirm repository is updated with all calendar scheduling features