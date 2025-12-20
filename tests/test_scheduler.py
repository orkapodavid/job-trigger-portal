"""
Unit tests for job scheduling logic.

Tests the calculate_next_run function to ensure jobs are scheduled correctly
with proper timezone handling.
"""

import unittest
from datetime import datetime, timezone, timedelta
from dateutil.relativedelta import relativedelta
import sys
import os

# Add parent directory to path to import app modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.utils import calculate_next_run
from app.models import ScheduledJob


class TestCalculateNextRunInterval(unittest.TestCase):
    """Test interval-based scheduling."""

    def test_interval_seconds(self):
        """Test job scheduled every 30 seconds."""
        job = ScheduledJob(
            name="Test Job",
            script_path="test.py",
            interval_seconds=30,
            schedule_type="interval",
            is_active=True
        )
        
        before = datetime.now(timezone.utc)
        next_run = calculate_next_run(job)
        after = datetime.now(timezone.utc)
        
        # Next run should be approximately 30 seconds from now
        expected_min = before + timedelta(seconds=30)
        expected_max = after + timedelta(seconds=30)
        
        self.assertGreaterEqual(next_run, expected_min)
        self.assertLessEqual(next_run, expected_max)

    def test_interval_minutes(self):
        """Test job scheduled every 5 minutes."""
        job = ScheduledJob(
            name="Test Job",
            script_path="test.py",
            interval_seconds=300,  # 5 minutes
            schedule_type="interval",
            is_active=True
        )
        
        before = datetime.now(timezone.utc)
        next_run = calculate_next_run(job)
        
        # Next run should be approximately 5 minutes from now
        expected = before + timedelta(minutes=5)
        delta = abs((next_run - expected).total_seconds())
        
        # Allow 1 second tolerance for execution time
        self.assertLess(delta, 1)

    def test_interval_hours(self):
        """Test job scheduled every 2 hours."""
        job = ScheduledJob(
            name="Test Job",
            script_path="test.py",
            interval_seconds=7200,  # 2 hours
            schedule_type="interval",
            is_active=True
        )
        
        before = datetime.now(timezone.utc)
        next_run = calculate_next_run(job)
        
        # Next run should be approximately 2 hours from now
        expected = before + timedelta(hours=2)
        delta = abs((next_run - expected).total_seconds())
        
        self.assertLess(delta, 1)

    def test_interval_none_schedule_type(self):
        """Test job with None schedule_type defaults to interval."""
        job = ScheduledJob(
            name="Test Job",
            script_path="test.py",
            interval_seconds=60,
            schedule_type=None,
            is_active=True
        )
        
        before = datetime.now(timezone.utc)
        next_run = calculate_next_run(job)
        
        # Should behave like interval type
        expected = before + timedelta(seconds=60)
        delta = abs((next_run - expected).total_seconds())
        
        self.assertLess(delta, 1)


class TestCalculateNextRunHourly(unittest.TestCase):
    """Test hourly scheduling."""

    def test_hourly_future_minute(self):
        """Test hourly job scheduled for a future minute in current hour."""
        now = datetime.now(timezone.utc)
        # Schedule for 5 minutes ahead
        target_minute = (now.minute + 5) % 60
        
        job = ScheduledJob(
            name="Test Job",
            script_path="test.py",
            interval_seconds=0,
            schedule_type="hourly",
            schedule_time=f"00:{target_minute:02d}",
            is_active=True
        )
        
        next_run = calculate_next_run(job)
        
        # Should be scheduled for target minute in current hour
        self.assertEqual(next_run.minute, target_minute)
        self.assertEqual(next_run.second, 0)
        self.assertEqual(next_run.microsecond, 0)
        
        # Should be in the future
        self.assertGreater(next_run, now)

    def test_hourly_past_minute(self):
        """Test hourly job scheduled for a past minute in current hour."""
        now = datetime.now(timezone.utc)
        # Schedule for 5 minutes ago
        target_minute = (now.minute - 5) % 60
        
        job = ScheduledJob(
            name="Test Job",
            script_path="test.py",
            interval_seconds=0,
            schedule_type="hourly",
            schedule_time=f"00:{target_minute:02d}",
            is_active=True
        )
        
        next_run = calculate_next_run(job)
        
        # Should be scheduled for target minute in next hour
        self.assertEqual(next_run.minute, target_minute)
        self.assertGreater(next_run, now)
        
        # Should be approximately 1 hour from now (allow for minute boundary variations)
        expected = now + timedelta(hours=1)
        delta = abs((next_run - expected).total_seconds())
        self.assertLess(delta, 600)  # Within 10 minutes tolerance


class TestCalculateNextRunDaily(unittest.TestCase):
    """Test daily scheduling with UTC time."""

    def test_daily_future_time_today(self):
        """Test daily job scheduled for later today (in UTC)."""
        now = datetime.now(timezone.utc)
        # Schedule for 2 hours from now
        target_time = now + timedelta(hours=2)
        
        job = ScheduledJob(
            name="Test Job",
            script_path="test.py",
            interval_seconds=0,
            schedule_type="daily",
            schedule_time=f"{target_time.hour:02d}:{target_time.minute:02d}",
            is_active=True
        )
        
        next_run = calculate_next_run(job)
        
        # Should be scheduled for today
        self.assertEqual(next_run.date(), now.date())
        self.assertEqual(next_run.hour, target_time.hour)
        self.assertEqual(next_run.minute, target_time.minute)

    def test_daily_past_time_today(self):
        """Test daily job scheduled for earlier today (in UTC)."""
        now = datetime.now(timezone.utc)
        # Schedule for 2 hours ago
        target_time = now - timedelta(hours=2)
        
        job = ScheduledJob(
            name="Test Job",
            script_path="test.py",
            interval_seconds=0,
            schedule_type="daily",
            schedule_time=f"{target_time.hour:02d}:{target_time.minute:02d}",
            is_active=True
        )
        
        next_run = calculate_next_run(job)
        
        # Should be scheduled for tomorrow
        tomorrow = now.date() + timedelta(days=1)
        self.assertEqual(next_run.date(), tomorrow)
        self.assertEqual(next_run.hour, target_time.hour)
        self.assertEqual(next_run.minute, target_time.minute)

    def test_daily_hkt_morning_converted_to_utc(self):
        """Test that 09:00 HKT (stored as 01:00 UTC) schedules correctly."""
        # This simulates a job that user created for 09:00 HKT
        # which state.py converted to 01:00 UTC before storing
        job = ScheduledJob(
            name="Test Job",
            script_path="test.py",
            interval_seconds=0,
            schedule_type="daily",
            schedule_time="01:00",  # 09:00 HKT in UTC
            is_active=True
        )
        
        next_run = calculate_next_run(job)
        
        # Should be scheduled for 01:00 UTC
        self.assertEqual(next_run.hour, 1)
        self.assertEqual(next_run.minute, 0)
        
        # Should be in the future
        now = datetime.now(timezone.utc)
        self.assertGreater(next_run, now)


class TestCalculateNextRunWeekly(unittest.TestCase):
    """Test weekly scheduling."""

    def test_weekly_same_day_future_time(self):
        """Test weekly job on same weekday, future time."""
        now = datetime.now(timezone.utc)
        current_weekday = now.weekday()
        target_time = now + timedelta(hours=2)
        
        job = ScheduledJob(
            name="Test Job",
            script_path="test.py",
            interval_seconds=0,
            schedule_type="weekly",
            schedule_time=f"{target_time.hour:02d}:{target_time.minute:02d}",
            schedule_day=current_weekday,
            is_active=True
        )
        
        next_run = calculate_next_run(job)
        
        # Should be scheduled for today
        self.assertEqual(next_run.weekday(), current_weekday)
        self.assertEqual(next_run.date(), now.date())

    def test_weekly_same_day_past_time(self):
        """Test weekly job on same weekday, past time."""
        now = datetime.now(timezone.utc)
        current_weekday = now.weekday()
        target_time = now - timedelta(hours=2)
        
        job = ScheduledJob(
            name="Test Job",
            script_path="test.py",
            interval_seconds=0,
            schedule_type="weekly",
            schedule_time=f"{target_time.hour:02d}:{target_time.minute:02d}",
            schedule_day=current_weekday,
            is_active=True
        )
        
        next_run = calculate_next_run(job)
        
        # Should be scheduled for next week
        self.assertEqual(next_run.weekday(), current_weekday)
        self.assertGreater(next_run, now + timedelta(days=6))

    def test_weekly_different_day(self):
        """Test weekly job on different weekday."""
        now = datetime.now(timezone.utc)
        current_weekday = now.weekday()
        target_weekday = (current_weekday + 3) % 7
        
        job = ScheduledJob(
            name="Test Job",
            script_path="test.py",
            interval_seconds=0,
            schedule_type="weekly",
            schedule_time="10:00",
            schedule_day=target_weekday,
            is_active=True
        )
        
        next_run = calculate_next_run(job)
        
        # Should be scheduled for target weekday
        self.assertEqual(next_run.weekday(), target_weekday)
        self.assertGreater(next_run, now)


class TestCalculateNextRunMonthly(unittest.TestCase):
    """Test monthly scheduling."""

    def test_monthly_future_day_this_month(self):
        """Test monthly job for a future day this month."""
        now = datetime.now(timezone.utc)
        
        # Find a day that's in the future this month
        target_day = min(now.day + 5, 28)  # Use 28 to avoid month-end issues
        
        if target_day <= now.day:
            # Skip if we can't find a future day
            self.skipTest("Cannot find future day in current month")
        
        job = ScheduledJob(
            name="Test Job",
            script_path="test.py",
            interval_seconds=0,
            schedule_type="monthly",
            schedule_time="10:00",
            schedule_day=target_day,
            is_active=True
        )
        
        next_run = calculate_next_run(job)
        
        # Should be scheduled for this month
        self.assertEqual(next_run.year, now.year)
        self.assertEqual(next_run.month, now.month)
        self.assertEqual(next_run.day, target_day)

    def test_monthly_past_day_this_month(self):
        """Test monthly job for a past day this month."""
        now = datetime.now(timezone.utc)
        
        # Use a day earlier in the month
        target_day = max(now.day - 5, 1)
        
        if target_day >= now.day:
            # Skip if we can't find a past day
            self.skipTest("Cannot find past day in current month")
        
        job = ScheduledJob(
            name="Test Job",
            script_path="test.py",
            interval_seconds=0,
            schedule_type="monthly",
            schedule_time="10:00",
            schedule_day=target_day,
            is_active=True
        )
        
        next_run = calculate_next_run(job)
        
        # Should be scheduled for next month
        expected = now + relativedelta(months=1, day=target_day, hour=10, minute=0, second=0, microsecond=0)
        self.assertEqual(next_run.day, target_day)
        self.assertGreater(next_run, now)

    def test_monthly_first_day(self):
        """Test monthly job on 1st of month."""
        job = ScheduledJob(
            name="Test Job",
            script_path="test.py",
            interval_seconds=0,
            schedule_type="monthly",
            schedule_time="09:00",
            schedule_day=1,
            is_active=True
        )
        
        next_run = calculate_next_run(job)
        
        # Should be scheduled for 1st
        self.assertEqual(next_run.day, 1)
        self.assertEqual(next_run.hour, 9)
        self.assertEqual(next_run.minute, 0)

    def test_monthly_last_day(self):
        """Test monthly job on 31st of month."""
        job = ScheduledJob(
            name="Test Job",
            script_path="test.py",
            interval_seconds=0,
            schedule_type="monthly",
            schedule_time="23:00",
            schedule_day=31,
            is_active=True
        )
        
        next_run = calculate_next_run(job)
        
        # Should handle 31st correctly (will adjust for months with fewer days)
        self.assertGreaterEqual(next_run.day, 28)
        self.assertLessEqual(next_run.day, 31)


class TestCalculateNextRunEdgeCases(unittest.TestCase):
    """Test edge cases and error handling."""

    def test_invalid_schedule_time_format(self):
        """Test handling of invalid schedule_time format."""
        job = ScheduledJob(
            name="Test Job",
            script_path="test.py",
            interval_seconds=0,
            schedule_type="daily",
            schedule_time="invalid",
            is_active=True
        )
        
        # Should not raise exception, should handle gracefully
        try:
            next_run = calculate_next_run(job)
            # Should default to midnight (00:00)
            self.assertEqual(next_run.hour, 0)
            self.assertEqual(next_run.minute, 0)
        except Exception:
            self.fail("calculate_next_run should handle invalid time format gracefully")

    def test_none_schedule_day_weekly(self):
        """Test weekly schedule with None day defaults to Monday."""
        job = ScheduledJob(
            name="Test Job",
            script_path="test.py",
            interval_seconds=0,
            schedule_type="weekly",
            schedule_time="10:00",
            schedule_day=None,
            is_active=True
        )
        
        next_run = calculate_next_run(job)
        
        # Should default to Monday (weekday 0)
        self.assertEqual(next_run.weekday(), 0)

    def test_none_schedule_day_monthly(self):
        """Test monthly schedule with None day defaults to 1st."""
        job = ScheduledJob(
            name="Test Job",
            script_path="test.py",
            interval_seconds=0,
            schedule_type="monthly",
            schedule_time="10:00",
            schedule_day=None,
            is_active=True
        )
        
        next_run = calculate_next_run(job)
        
        # Should default to 1st of month
        self.assertEqual(next_run.day, 1)

    def test_timezone_awareness(self):
        """Test that all returned datetimes are timezone-aware UTC."""
        test_cases = [
            ("interval", None, None),
            ("hourly", "30", None),
            ("daily", "15:00", None),
            ("weekly", "10:00", 2),
            ("monthly", "09:00", 15),
        ]
        
        for schedule_type, schedule_time, schedule_day in test_cases:
            job = ScheduledJob(
                name="Test Job",
                script_path="test.py",
                interval_seconds=3600,
                schedule_type=schedule_type,
                schedule_time=schedule_time if schedule_time else "00:00",
                schedule_day=schedule_day,
                is_active=True
            )
            
            next_run = calculate_next_run(job)
            
            # Verify timezone awareness
            self.assertIsNotNone(next_run.tzinfo, 
                                f"Next run for {schedule_type} should be timezone-aware")
            self.assertEqual(next_run.tzinfo, timezone.utc,
                           f"Next run for {schedule_type} should be in UTC")


if __name__ == '__main__':
    unittest.main()
