import sys
import datetime
import time


def main():
    print(f"[{datetime.datetime.now()}] Starting Test Job Execution...")
    print("Step 1: Initialization complete.")
    time.sleep(1)
    print("Step 2: Processing data...", file=sys.stdout)
    print("Info: Use of simulated resources detected.", file=sys.stderr)
    time.sleep(1)
    print("Step 3: Finalizing...")
    print(f"[{datetime.datetime.now()}] Job Completed Successfully.")
    sys.exit(0)


if __name__ == "__main__":
    main()