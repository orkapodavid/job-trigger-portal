"""
Manual migration to add columns to existing scheduled_jobs table.

SQLite has limited ALTER TABLE support, so we need to add columns explicitly.
"""
import sqlite3
import sys

def migrate():
    print("=" * 60)
    print("Adding columns to scheduled_jobs table")
    print("=" * 60)
    
    db_path = "reflex.db"
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if columns already exist
        cursor.execute("PRAGMA table_info(scheduled_jobs)")
        columns = [row[1] for row in cursor.fetchall()]
        
        print(f"\nCurrent columns in scheduled_jobs: {', '.join(columns)}")
        
        # Add last_dispatched_at if it doesn't exist
        if 'last_dispatched_at' not in columns:
            print("\nAdding column: last_dispatched_at...")
            cursor.execute("ALTER TABLE scheduled_jobs ADD COLUMN last_dispatched_at DATETIME")
            print("✓ Added last_dispatched_at")
        else:
            print("\n✓ Column last_dispatched_at already exists")
        
        # Add dispatch_lock_until if it doesn't exist
        if 'dispatch_lock_until' not in columns:
            print("Adding column: dispatch_lock_until...")
            cursor.execute("ALTER TABLE scheduled_jobs ADD COLUMN dispatch_lock_until DATETIME")
            print("✓ Added dispatch_lock_until")
        else:
            print("✓ Column dispatch_lock_until already exists")
        
        conn.commit()
        conn.close()
        
        print("\n" + "=" * 60)
        print("✅ Columns added successfully!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    migrate()
