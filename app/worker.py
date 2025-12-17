import asyncio
import json
import logging
import os
import platform
import subprocess
import sys
import uuid
from datetime import datetime, timezone
import websockets

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("Worker")
SERVER_URL = os.getenv("REFLEX_SERVER_URL", "ws://localhost:8000/ws/heartbeat")
WORKER_ID = f"worker-{uuid.uuid4().hex[:8]}"
start_time = datetime.now(timezone.utc)
jobs_processed = 0
running = True
send_queue = asyncio.Queue()


async def execute_job(job_id: int, script_path: str):
    """
    Execute the script in a subprocess.
    This runs in a thread to verify it doesn't block the asyncio loop.
    """
    global jobs_processed
    logger.info(f"Executing job {job_id}: {script_path}")
    await send_queue.put(
        {
            "type": "event",
            "event": "job_started",
            "job_id": job_id,
            "worker_id": WORKER_ID,
        }
    )
    status = "UNKNOWN"
    log_output = ""
    if not os.path.exists(script_path):
        status = "ERROR"
        log_output = f"Script not found: {script_path}"
    else:
        try:
            cmd = [script_path]
            if script_path.endswith(".py"):
                cmd = [sys.executable, script_path]
            elif script_path.endswith(".sh"):
                cmd = ["/bin/bash", script_path]
            elif script_path.endswith(".bat"):
                cmd = ["cmd.exe", "/c", script_path]

            def run_subprocess():
                return subprocess.run(cmd, capture_output=True, text=True, timeout=300)

            process = await asyncio.to_thread(run_subprocess)
            log_output = f"STDOUT:\n{process.stdout}\n\nSTDERR:\n{process.stderr}"
            if process.returncode == 0:
                status = "SUCCESS"
            else:
                status = "FAILURE"
                log_output += f"\n\nExit Code: {process.returncode}"
        except subprocess.TimeoutExpired as e:
            status = "FAILURE"
            log_output = "Execution timed out after 300 seconds."
            logger.exception(f"Timeout executing job {job_id}: {e}")
        except Exception as e:
            status = "ERROR"
            log_output = f"Execution error: {str(e)}"
            logger.exception(f"Job {job_id} error: {e}")
    jobs_processed += 1
    result_msg = {
        "type": "job_result",
        "job_id": job_id,
        "status": status,
        "log_output": log_output,
        "run_time": datetime.now(timezone.utc).isoformat(),
        "worker_id": WORKER_ID,
    }
    await send_queue.put(result_msg)
    logger.info(f"Job {job_id} finished with status {status}")


async def sender_task(ws):
    """Task to send messages from the queue to the websocket."""
    try:
        while running:
            msg = await send_queue.get()
            await ws.send(json.dumps(msg))
            send_queue.task_done()
    except asyncio.CancelledError as e:
        logger.exception(f"Sender task cancelled: {e}")
    except Exception as e:
        logger.exception(f"Sender task error: {e}")


async def heartbeat_task():
    """Task to enqueue heartbeat messages periodically."""
    while running:
        try:
            uptime = (datetime.now(timezone.utc) - start_time).total_seconds()
            hb_msg = {
                "type": "heartbeat",
                "worker_id": WORKER_ID,
                "status": "idle",
                "jobs_processed": jobs_processed,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "uptime_seconds": int(uptime),
            }
            await send_queue.put(hb_msg)
            await asyncio.sleep(60)
        except asyncio.CancelledError as e:
            logger.exception(f"Heartbeat task cancelled: {e}")
            break


async def connection_handler():
    """Main websocket connection loop."""
    retry_delay = 5
    while running:
        try:
            async with websockets.connect(SERVER_URL) as ws:
                logger.info(f"Connected to {SERVER_URL}")
                reg_msg = {
                    "type": "worker_register",
                    "worker_id": WORKER_ID,
                    "platform": platform.system(),
                    "hostname": platform.node(),
                }
                await ws.send(json.dumps(reg_msg))
                sender = asyncio.create_task(sender_task(ws))
                try:
                    async for message in ws:
                        data = json.loads(message)
                        msg_type = data.get("type")
                        if msg_type == "execute_job":
                            job_id = data.get("job_id")
                            script_path = data.get("script_path")
                            if job_id and script_path:
                                asyncio.create_task(execute_job(job_id, script_path))
                        elif msg_type == "ack":
                            pass
                except websockets.ConnectionClosed as e:
                    logger.exception(f"Connection closed by server: {e}")
                finally:
                    sender.cancel()
        except (OSError, asyncio.TimeoutError) as e:
            logger.exception(f"Connection failed: {e}. Retrying in {retry_delay}s...")
            await asyncio.sleep(retry_delay)
            retry_delay = min(retry_delay * 2, 60)
        except Exception as e:
            logger.exception(f"Unexpected error: {e}")
            await asyncio.sleep(5)


def main():
    logger.info(f"Worker {WORKER_ID} starting...")
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.create_task(heartbeat_task())
        loop.run_until_complete(connection_handler())
    except KeyboardInterrupt as e:
        logger.exception(f"Worker stopped by user: {e}")


if __name__ == "__main__":
    main()
