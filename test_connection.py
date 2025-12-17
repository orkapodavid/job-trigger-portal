"""
Quick test script to verify WebSocket connection stability and job execution.
"""
import asyncio
import sys
from datetime import datetime, timezone, timedelta
from sqlmodel import Session, select, create_engine
from app.models import ScheduledJob, get_db_url

def create_test_job():
    """Create a test job scheduled to run immediately."""
    engine = create_engine(get_db_url())
    
    # Calculate next run time (5 seconds from now)
    next_run = datetime.now(timezone.utc) + timedelta(seconds=5)
    
    test_job = ScheduledJob(
        name="Test Job - Connection Stability",
        script_path="app/scripts/test_job.py",
        schedule_type="interval",
        interval_value=1,  # Run every hour
        interval_unit="hours",
        interval_seconds=3600,  # 1 hour in seconds
        is_active=True,
        next_run=next_run,
    )
    
    with Session(engine) as session:
        # Check if test job already exists
        existing = session.exec(
            select(ScheduledJob).where(ScheduledJob.name == test_job.name)
        ).first()
        
        if existing:
            print(f"✓ Test job already exists (ID: {existing.id})")
            print(f"  Next run: {existing.next_run}")
            return existing.id
        else:
            session.add(test_job)
            session.commit()
            session.refresh(test_job)
            print(f"✓ Test job created (ID: {test_job.id})")
            print(f"  Next run: {test_job.next_run}")
            return test_job.id

if __name__ == "__main__":
    print("=" * 60)
    print("WebSocket Connection & Job Execution Test")
    print("=" * 60)
    print(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")
    print()
    
    try:
        job_id = create_test_job()
        print()
        print("✓ Test job scheduled successfully!")
        print()
        print("Next steps:")
        print("1. Monitor the worker terminal for job execution")
        print("2. Job should execute in ~5 seconds")
        print("3. Verify worker connection remains stable")
        print("4. Check the UI at http://localhost:3000/ for results")
        print()
    except Exception as e:
        print(f"✗ Error creating test job: {e}")
        sys.exit(1)
