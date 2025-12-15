"""
Verification script to test timezone conversion fix.
Tests the actual timezone conversion logic independently.
"""

from datetime import datetime, timezone
import pytz

# Initialize HKT timezone
HKT = pytz.timezone("Asia/Hong_Kong")

def hkt_to_utc_schedule_test(schedule_type: str, time_str: str, day_val: int = None):
    """Test version of HKT to UTC conversion."""
    if not time_str:
        return (time_str, day_val)
    
    h, m = map(int, time_str.split(":"))
    dt_hkt = None
    
    if schedule_type == "daily":
        dt_hkt = HKT.localize(datetime(2024, 1, 1, h, m, 0))
    elif schedule_type == "weekly":
        dt_hkt = HKT.localize(datetime(2024, 1, 1 + (day_val or 0), h, m, 0))
    elif schedule_type == "monthly":
        dt_hkt = HKT.localize(datetime(2024, 1, day_val or 1, h, m, 0))
    else:
        return (time_str, day_val)
    
    dt_utc = dt_hkt.astimezone(timezone.utc)
    new_time = dt_utc.strftime("%H:%M")
    new_day = None
    
    if schedule_type == "weekly":
        new_day = dt_utc.weekday()
    elif schedule_type == "monthly":
        new_day = dt_utc.day
    
    return (new_time, new_day)


def run_tests():
    """Run verification tests."""
    print("=" * 60)
    print("TIMEZONE CONVERSION VERIFICATION")
    print("=" * 60)
    
    tests = [
        {
            "name": "Daily 09:00 HKT -> UTC",
            "type": "daily",
            "hkt_time": "09:00",
            "day": None,
            "expected_utc": "01:00",
            "expected_day": None
        },
        {
            "name": "Daily 22:00 HKT -> UTC",
            "type": "daily",
            "hkt_time": "22:00",
            "day": None,
            "expected_utc": "14:00",
            "expected_day": None
        },
        {
            "name": "Daily 00:00 HKT -> UTC (day boundary)",
            "type": "daily",
            "hkt_time": "00:00",
            "day": None,
            "expected_utc": "16:00",
            "expected_day": None
        },
        {
            "name": "Weekly Monday 09:00 HKT -> UTC",
            "type": "weekly",
            "hkt_time": "09:00",
            "day": 0,
            "expected_utc": "01:00",
            "expected_day": 0
        },
        {
            "name": "Weekly Sunday 02:00 HKT -> UTC (day rollback)",
            "type": "weekly",
            "hkt_time": "02:00",
            "day": 6,
            "expected_utc": "18:00",
            "expected_day": 5  # Saturday
        },
        {
            "name": "Monthly 1st 09:00 HKT -> UTC",
            "type": "monthly",
            "hkt_time": "09:00",
            "day": 1,
            "expected_utc": "01:00",
            "expected_day": 1
        },
        {
            "name": "Monthly 15th 01:00 HKT -> UTC (day rollback)",
            "type": "monthly",
            "hkt_time": "01:00",
            "day": 15,
            "expected_utc": "17:00",
            "expected_day": 14
        }
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        result_time, result_day = hkt_to_utc_schedule_test(
            test["type"],
            test["hkt_time"],
            test["day"]
        )
        
        time_match = result_time == test["expected_utc"]
        day_match = result_day == test["expected_day"]
        success = time_match and day_match
        
        if success:
            passed += 1
            status = "✓ PASS"
        else:
            failed += 1
            status = "✗ FAIL"
        
        print(f"\n{status} - {test['name']}")
        print(f"  Input:    {test['hkt_time']} HKT" + (f" (day {test['day']})" if test['day'] is not None else ""))
        print(f"  Expected: {test['expected_utc']} UTC" + (f" (day {test['expected_day']})" if test['expected_day'] is not None else ""))
        print(f"  Got:      {result_time} UTC" + (f" (day {result_day})" if result_day is not None else ""))
        
        if not success:
            if not time_match:
                print(f"  ERROR: Time mismatch!")
            if not day_match:
                print(f"  ERROR: Day mismatch!")
    
    print("\n" + "=" * 60)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("=" * 60)
    
    # Verify HKT offset
    print("\nVERIFYING HKT TIMEZONE OFFSET:")
    dt_naive = datetime(2024, 12, 15, 12, 0, 0)
    dt_hkt = HKT.localize(dt_naive)
    offset_seconds = dt_hkt.utcoffset().total_seconds()
    offset_hours = offset_seconds / 3600
    print(f"  HKT offset: +{offset_hours:.1f} hours (expected +8.0)")
    
    if offset_hours == 8.0:
        print("  ✓ HKT offset is correct")
    else:
        print(f"  ✗ HKT offset is WRONG! Got +{offset_hours}, expected +8.0")
    
    return failed == 0


if __name__ == "__main__":
    success = run_tests()
    exit(0 if success else 1)
