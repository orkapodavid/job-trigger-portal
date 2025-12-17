"""
Database Migration Script

Creates or updates database schema to include new tables:
- WorkerRegistration
- JobDispatch
- Adds new columns to ScheduledJob (last_dispatched_at, dispatch_lock_until)
"""
import sys
from sqlmodel import SQLModel, create_engine
from app.models import (
    ScheduledJob,
    JobExecutionLog,
    WorkerRegistration,
    JobDispatch,
    get_db_url,
)

def migrate():
    """Run database migration."""
    print("=" * 60)
    print("Database Migration - Job Scheduler")
    print("=" * 60)
    
    db_url = get_db_url()
    print(f"\nDatabase URL: {db_url}")
    print("\nThis will create/update the following tables:")
    print("  - worker_registration (NEW)")
    print("  - job_dispatch (NEW)")
    print("  - scheduled_jobs (ADD COLUMNS: last_dispatched_at, dispatch_lock_until)")
    print("  - job_execution_logs (no changes)")
    
    # Check for --force flag
    if "--force" not in sys.argv:
        response = input("\nProceed with migration? (yes/no): ")
        if response.lower() not in ['yes', 'y']:
            print("Migration cancelled.")
            sys.exit(0)
    else:
        print("\n--force flag detected, proceeding with migration...")
    
    try:
        print("\nConnecting to database...")
        engine = create_engine(db_url, echo=True)
        
        print("\nCreating/updating tables...")
        SQLModel.metadata.create_all(engine)
        
        print("\n" + "=" * 60)
        print("✅ Migration completed successfully!")
        print("=" * 60)
        print("\nNext steps:")
        print("1. Start the scheduler service:")
        print("   python -m services.scheduler_service")
        print("\n2. Start one or more worker services:")
        print("   python -m services.worker_service")
        print("\n3. Start the Reflex web portal:")
        print("   reflex run")
        print()
        
    except Exception as e:
        print("\n" + "=" * 60)
        print(f"❌ Migration failed: {e}")
        print("=" * 60)
        sys.exit(1)

if __name__ == "__main__":
    migrate()
