# Test Suite for Job Trigger Portal

This directory contains comprehensive tests for the Job Trigger Portal application, with a focus on timezone handling and scheduling logic.

## Test Files

### `verify_timezone_fix.py` ⭐ Quick Start

**Purpose:** Standalone verification script for timezone conversion accuracy.

**Run:**
```bash
python tests/verify_timezone_fix.py
```

**Features:**
- No dependencies on full application
- Only requires `pytz` library
- 7 core test scenarios
- Clear pass/fail output
- Tests all schedule types (daily, weekly, monthly)
- Verifies HKT timezone offset accuracy

**Use this when:** You want to quickly verify timezone conversion is working correctly without running the full test suite.

### `test_timezone_service.py`

**Purpose:** Comprehensive unit tests for timezone conversion functions.

**Coverage:**
- 20+ test cases for `hkt_to_utc_schedule()` and `utc_to_hkt_schedule()`
- Daily, weekly, and monthly schedule conversions
- Edge cases (day boundaries, week/month rollovers)
- Roundtrip conversions (HKT→UTC→HKT)
- Error handling (empty/invalid inputs)
- All 24 hours and all 7 weekdays

**Run:**
```bash
python -m unittest tests.test_timezone_service
```

### `test_scheduler.py`

**Purpose:** Unit tests for job scheduling logic in the worker.

**Coverage:**
- 30+ test cases for `calculate_next_run()` function
- Interval-based scheduling (seconds, minutes, hours)
- Hourly scheduling (specific minute each hour)
- Daily scheduling (specific time each day)
- Weekly scheduling (specific day and time)
- Monthly scheduling (specific day of month and time)
- Edge cases and error handling
- Timezone awareness validation

**Run:**
```bash
python -m unittest tests.test_scheduler
```

## Test Results

All tests currently passing:

```
✓ 7/7 core verification tests passing
✓ 20+ timezone conversion tests passing
✓ 30+ scheduler logic tests passing
✓ 100% test success rate
```

## Running All Tests

### Option 1: Using unittest
```bash
python -m unittest discover tests
```

### Option 2: Using pytest (if installed)
```bash
pytest tests/ -v
```

### Option 3: Individual test files
```bash
python -m unittest tests.test_timezone_service -v
python -m unittest tests.test_scheduler -v
python tests/verify_timezone_fix.py
```

## Test Scenarios Covered

### Timezone Conversion
- ✅ HKT morning times → UTC (e.g., 09:00 HKT → 01:00 UTC)
- ✅ HKT evening times → UTC (e.g., 22:00 HKT → 14:00 UTC)
- ✅ HKT midnight → UTC previous day (e.g., 00:00 HKT → 16:00 UTC)
- ✅ Weekly day rollback (e.g., Sunday 02:00 HKT → Saturday 18:00 UTC)
- ✅ Monthly day rollback (e.g., 1st 05:00 HKT → previous month last day)
- ✅ Roundtrip conversions maintain accuracy
- ✅ HKT timezone offset is exactly +08:00

### Scheduling Logic
- ✅ Interval schedules (every N seconds/minutes/hours)
- ✅ Hourly schedules (specific minute each hour)
- ✅ Daily schedules (specific time each day in UTC)
- ✅ Weekly schedules (specific day and time in UTC)
- ✅ Monthly schedules (specific day of month and time in UTC)
- ✅ Past vs. future time handling
- ✅ Day boundary crossing
- ✅ Timezone awareness of all datetime objects

## Prerequisites

### Required
- Python 3.11+
- `pytz` library

### Optional (for full app tests)
- `reflex` framework
- `sqlmodel` ORM
- `python-dateutil`
- All dependencies in `requirements.txt`

## Continuous Integration

These tests are designed to be run in CI/CD pipelines:

```yaml
# Example GitHub Actions workflow
- name: Run timezone tests
  run: python tests/verify_timezone_fix.py

- name: Run full test suite
  run: python -m unittest discover tests
```

## Test Development Guidelines

When adding new tests:

1. **Test one thing:** Each test should verify a single behavior
2. **Use descriptive names:** `test_daily_future_time_today` is better than `test_case_1`
3. **Include edge cases:** Day boundaries, month-end, leap years, etc.
4. **Document expected behavior:** Use docstrings to explain what's being tested
5. **Verify timezone awareness:** All datetime objects should have tzinfo set

## Known Limitations

- Tests use fixed dates (2024-01-01) for predictable day-of-week calculations
- Does not test actual job execution (that's integration testing)
- Does not test database interactions (uses in-memory objects)
- Does not test Reflex UI components (unit tests only)

## Troubleshooting

### Import errors
```
ModuleNotFoundError: No module named 'reflex'
```
**Solution:** Some tests require the full application. Use `verify_timezone_fix.py` which has no app dependencies.

### Wrong timezone offset
```
HKT offset: +7.6 hours (expected +8.0)
```
**Solution:** You're using `datetime(..., tzinfo=tz)` instead of `tz.localize()`. See `TIMEZONE_FIX.md` for details.

### Tests pass but jobs run at wrong time
**Solution:** Check that `app/state.py` uses `HKT.localize()` method. Recreate jobs created before the fix.

## Related Documentation

- [`TIMEZONE_FIX.md`](../TIMEZONE_FIX.md) - Technical details of timezone bug fix
- [`PHASE1_SUMMARY.md`](../PHASE1_SUMMARY.md) - Phase 1 implementation summary
- [`plan.md`](../plan.md) - Development roadmap

## Contributing

When adding new features that involve time handling:

1. Write tests first (TDD approach)
2. Include timezone edge cases
3. Verify with `verify_timezone_fix.py`
4. Update this README with new test coverage

---

**Last Updated:** December 15, 2024  
**Test Suite Version:** 1.0  
**Status:** All tests passing ✓
