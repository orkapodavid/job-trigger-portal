"""
Unit tests for timezone conversion functions.

Tests the correct conversion between HKT (UTC+8) and UTC for job scheduling.
"""

import unittest
from datetime import datetime, timezone
import pytz
import sys
import os

# Add parent directory to path to import app modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.state import hkt_to_utc_schedule, utc_to_hkt_schedule


class TestTimezoneConversion(unittest.TestCase):
    """Test timezone conversion functions."""

    def test_hkt_to_utc_daily_morning(self):
        """Test converting 09:00 HKT to UTC for daily schedule."""
        time_str = "09:00"
        schedule_type = "daily"
        
        utc_time, utc_day = hkt_to_utc_schedule(schedule_type, time_str, None)
        
        # 09:00 HKT = 01:00 UTC
        self.assertEqual(utc_time, "01:00")
        self.assertIsNone(utc_day)

    def test_hkt_to_utc_daily_evening(self):
        """Test converting 22:00 HKT to UTC for daily schedule."""
        time_str = "22:00"
        schedule_type = "daily"
        
        utc_time, utc_day = hkt_to_utc_schedule(schedule_type, time_str, None)
        
        # 22:00 HKT = 14:00 UTC (same day)
        self.assertEqual(utc_time, "14:00")
        self.assertIsNone(utc_day)

    def test_hkt_to_utc_daily_midnight(self):
        """Test converting 00:00 HKT to UTC for daily schedule."""
        time_str = "00:00"
        schedule_type = "daily"
        
        utc_time, utc_day = hkt_to_utc_schedule(schedule_type, time_str, None)
        
        # 00:00 HKT = 16:00 UTC (previous day)
        self.assertEqual(utc_time, "16:00")
        self.assertIsNone(utc_day)

    def test_hkt_to_utc_weekly_monday_morning(self):
        """Test converting Monday 09:00 HKT to UTC for weekly schedule."""
        time_str = "09:00"
        schedule_type = "weekly"
        day_val = 0  # Monday in HKT
        
        utc_time, utc_day = hkt_to_utc_schedule(schedule_type, time_str, day_val)
        
        # Monday 09:00 HKT = Monday 01:00 UTC (same day)
        self.assertEqual(utc_time, "01:00")
        self.assertEqual(utc_day, 0)  # Still Monday

    def test_hkt_to_utc_weekly_sunday_early_morning(self):
        """Test converting Sunday 02:00 HKT to UTC for weekly schedule."""
        time_str = "02:00"
        schedule_type = "weekly"
        day_val = 6  # Sunday in HKT
        
        utc_time, utc_day = hkt_to_utc_schedule(schedule_type, time_str, day_val)
        
        # Sunday 02:00 HKT = Saturday 18:00 UTC (previous day)
        self.assertEqual(utc_time, "18:00")
        self.assertEqual(utc_day, 5)  # Saturday

    def test_hkt_to_utc_monthly_first_day(self):
        """Test converting 1st day 09:00 HKT to UTC for monthly schedule."""
        time_str = "09:00"
        schedule_type = "monthly"
        day_val = 1
        
        utc_time, utc_day = hkt_to_utc_schedule(schedule_type, time_str, day_val)
        
        # 1st 09:00 HKT = 1st 01:00 UTC (same day)
        self.assertEqual(utc_time, "01:00")
        self.assertEqual(utc_day, 1)

    def test_hkt_to_utc_monthly_early_morning(self):
        """Test converting 15th day 01:00 HKT to UTC for monthly schedule."""
        time_str = "01:00"
        schedule_type = "monthly"
        day_val = 15
        
        utc_time, utc_day = hkt_to_utc_schedule(schedule_type, time_str, day_val)
        
        # 15th 01:00 HKT = 14th 17:00 UTC (previous day)
        self.assertEqual(utc_time, "17:00")
        self.assertEqual(utc_day, 14)

    def test_utc_to_hkt_daily_morning(self):
        """Test converting 01:00 UTC to HKT for daily schedule."""
        time_str = "01:00"
        schedule_type = "daily"
        
        hkt_time, hkt_day = utc_to_hkt_schedule(schedule_type, time_str, None)
        
        # 01:00 UTC = 09:00 HKT
        self.assertEqual(hkt_time, "09:00")
        self.assertIsNone(hkt_day)

    def test_utc_to_hkt_daily_afternoon(self):
        """Test converting 14:00 UTC to HKT for daily schedule."""
        time_str = "14:00"
        schedule_type = "daily"
        
        hkt_time, hkt_day = utc_to_hkt_schedule(schedule_type, time_str, None)
        
        # 14:00 UTC = 22:00 HKT
        self.assertEqual(hkt_time, "22:00")
        self.assertIsNone(hkt_day)

    def test_utc_to_hkt_weekly_roundtrip(self):
        """Test roundtrip conversion for weekly schedule."""
        original_time = "15:30"
        original_day = 3  # Thursday in HKT
        schedule_type = "weekly"
        
        # Convert to UTC
        utc_time, utc_day = hkt_to_utc_schedule(schedule_type, original_time, original_day)
        
        # Convert back to HKT
        hkt_time, hkt_day = utc_to_hkt_schedule(schedule_type, utc_time, utc_day)
        
        # Should match original values
        self.assertEqual(hkt_time, original_time)
        self.assertEqual(hkt_day, original_day)

    def test_utc_to_hkt_monthly_roundtrip(self):
        """Test roundtrip conversion for monthly schedule."""
        original_time = "23:45"
        original_day = 20
        schedule_type = "monthly"
        
        # Convert to UTC
        utc_time, utc_day = hkt_to_utc_schedule(schedule_type, original_time, original_day)
        
        # Convert back to HKT
        hkt_time, hkt_day = utc_to_hkt_schedule(schedule_type, utc_time, utc_day)
        
        # Should match original values
        self.assertEqual(hkt_time, original_time)
        self.assertEqual(hkt_day, original_day)

    def test_hkt_to_utc_empty_time(self):
        """Test handling of empty time string."""
        time_str = ""
        schedule_type = "daily"
        
        result_time, result_day = hkt_to_utc_schedule(schedule_type, time_str, None)
        
        self.assertEqual(result_time, "")
        self.assertIsNone(result_day)

    def test_hkt_to_utc_none_time(self):
        """Test handling of None time string."""
        time_str = None
        schedule_type = "daily"
        
        result_time, result_day = hkt_to_utc_schedule(schedule_type, time_str, None)
        
        self.assertIsNone(result_time)
        self.assertIsNone(result_day)

    def test_hkt_to_utc_interval_type(self):
        """Test that interval schedule type returns unchanged values."""
        time_str = "09:00"
        schedule_type = "interval"
        
        result_time, result_day = hkt_to_utc_schedule(schedule_type, time_str, None)
        
        # Interval type should not convert
        self.assertEqual(result_time, time_str)
        self.assertIsNone(result_day)

    def test_hkt_offset_is_correct(self):
        """Verify HKT timezone offset is exactly +08:00."""
        HKT = pytz.timezone("Asia/Hong_Kong")
        dt_naive = datetime(2024, 12, 15, 12, 0, 0)
        dt_hkt = HKT.localize(dt_naive)
        
        # Get offset in hours
        offset_seconds = dt_hkt.utcoffset().total_seconds()
        offset_hours = offset_seconds / 3600
        
        self.assertEqual(offset_hours, 8.0)


class TestTimezoneEdgeCases(unittest.TestCase):
    """Test edge cases and boundary conditions."""

    def test_day_boundary_crossing_forward(self):
        """Test when HKT time crosses into next day in UTC."""
        # 23:00 HKT should become 15:00 UTC same day
        time_str = "23:00"
        schedule_type = "daily"
        
        utc_time, _ = hkt_to_utc_schedule(schedule_type, time_str, None)
        
        self.assertEqual(utc_time, "15:00")

    def test_day_boundary_crossing_backward(self):
        """Test when HKT time crosses into previous day in UTC."""
        # 01:00 HKT should become 17:00 UTC previous day
        time_str = "01:00"
        schedule_type = "daily"
        
        utc_time, _ = hkt_to_utc_schedule(schedule_type, time_str, None)
        
        self.assertEqual(utc_time, "17:00")

    def test_weekly_day_rollover_backward(self):
        """Test weekly schedule when UTC day rolls backward."""
        # Monday 03:00 HKT = Sunday 19:00 UTC
        time_str = "03:00"
        schedule_type = "weekly"
        day_val = 0  # Monday
        
        utc_time, utc_day = hkt_to_utc_schedule(schedule_type, time_str, day_val)
        
        self.assertEqual(utc_time, "19:00")
        self.assertEqual(utc_day, 6)  # Sunday (previous day)

    def test_monthly_day_rollover_backward(self):
        """Test monthly schedule when UTC day rolls backward."""
        # 1st 05:00 HKT should become previous month's last day 21:00 UTC
        # But we use fixed year/month in conversion, so day becomes 31st (of previous month conceptually)
        time_str = "05:00"
        schedule_type = "monthly"
        day_val = 1
        
        utc_time, utc_day = hkt_to_utc_schedule(schedule_type, time_str, day_val)
        
        self.assertEqual(utc_time, "21:00")
        # Day rolls back to 31 (last day of previous month in our test setup)
        self.assertLess(utc_day, day_val)

    def test_all_hours_daily(self):
        """Test all 24 hours convert correctly for daily schedule."""
        schedule_type = "daily"
        
        for hour in range(24):
            time_str = f"{hour:02d}:00"
            utc_time, _ = hkt_to_utc_schedule(schedule_type, time_str, None)
            
            # Verify it's a valid time string
            self.assertIsNotNone(utc_time)
            self.assertRegex(utc_time, r'^\d{2}:\d{2}$')
            
            # Verify roundtrip
            hkt_time, _ = utc_to_hkt_schedule(schedule_type, utc_time, None)
            self.assertEqual(hkt_time, time_str)

    def test_all_weekdays(self):
        """Test all weekdays convert correctly for weekly schedule."""
        schedule_type = "weekly"
        time_str = "12:00"
        
        for day in range(7):
            utc_time, utc_day = hkt_to_utc_schedule(schedule_type, time_str, day)
            
            # Verify day is valid
            self.assertGreaterEqual(utc_day, 0)
            self.assertLess(utc_day, 7)
            
            # Verify roundtrip
            hkt_time, hkt_day = utc_to_hkt_schedule(schedule_type, utc_time, utc_day)
            self.assertEqual(hkt_time, time_str)
            self.assertEqual(hkt_day, day)


if __name__ == '__main__':
    unittest.main()
