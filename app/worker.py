import asyncio
import json
import logging
import os
import platform
import subprocess
import sys
import time
import traceback
import uuid
import websockets

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("Worker")
SERVER_URL = os.getenv("REFLEX_SERVER_URL", "ws://localhost:8000/ws/heartbeat")
WORKER_ID = f"worker-{uuid.uuid4().hex[:8]}"
HEARTBEAT_INTERVAL = 30
RECONNECT_DELAY = 5


class WorkerClient:
    def __init__(self):
        self.websocket = None
        self.is_running = False
        self.jobs_processed = 0
        self.start_time = time.time()

    async def connect(self):
        while True:
            try:
                logger.info(f"Connecting to {SERVER_URL}...")
                async with websockets.connect(SERVER_URL) as websocket:
                    self.websocket = websocket
                    self.is_running = True
                    logger.info(f"Connected! Worker ID: {WORKER_ID}")
                    await self.send_registration()
                    heartbeat_task = asyncio.create_task(self.heartbeat_loop())
                    try:
                        async for message in websocket:
                            await self.handle_message(message)
                    except websockets.ConnectionClosed:
                        logger.exception("Connection closed by server.")
                    finally:
                        self.is_running = False
                        heartbeat_task.cancel()
                        try:
                            await heartbeat_task
                        except asyncio.CancelledError:
                            logger.exception("Heartbeat task cancelled")
            except Exception as e:
                logger.exception(f"Connection error: {e}")
                await asyncio.sleep(RECONNECT_DELAY)

    async def send_registration(self):
        reg_msg = {
            "type": "worker_register",
            "worker_id": WORKER_ID,
            "platform": platform.platform(),
            "python_version": platform.python_version(),
            "hostname": platform.node(),
        }
        await self.send_json(reg_msg)

    async def heartbeat_loop(self):
        while self.is_running:
            try:
                uptime = int(time.time() - self.start_time)
                hb_msg = {
                    "type": "heartbeat",
                    "worker_id": WORKER_ID,
                    "status": "idle",
                    "jobs_processed": self.jobs_processed,
                    "uptime_seconds": uptime,
                    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                }
                await self.send_json(hb_msg)
                await asyncio.sleep(HEARTBEAT_INTERVAL)
            except Exception as e:
                logger.exception(f"Error in heartbeat: {e}")
                break

    async def send_json(self, data: dict):
        if self.websocket:
            await self.websocket.send(json.dumps(data))

    async def handle_message(self, message: str):
        try:
            data = json.loads(message)
            msg_type = data.get("type")
            if msg_type == "execute_job":
                await self.execute_job(data)
            elif msg_type == "ack":
                pass
            else:
                logger.debug(f"Unknown message type: {msg_type}")
        except json.JSONDecodeError:
            logger.exception("Received invalid JSON")
        except Exception as e:
            logger.exception(f"Error handling message: {e}")

    async def execute_job(self, data: dict):
        job_id = data.get("job_id")
        script_path = data.get("script_path")
        script_args = data.get("script_args")
        logger.info(f"Executing job {job_id}: {script_path} (Args: {script_args})")
        await self.send_json(
            {
                "type": "event",
                "event": "job_started",
                "job_id": job_id,
                "worker_id": WORKER_ID,
            }
        )
        status = "FAILURE"
        log_output = ""
        start_ts = time.time()
        try:
            if not os.path.exists(script_path):
                raise FileNotFoundError(f"Script not found: {script_path}")
            cmd = [sys.executable, script_path]
            if script_args:
                import shlex

                cmd.extend(shlex.split(script_args))
            process = await asyncio.create_subprocess_exec(
                *cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            return_code = process.returncode
            log_output = (
                stdout.decode().strip()
                + """
"""
                + stderr.decode().strip()
            )
            status = "SUCCESS" if return_code == 0 else "FAILURE"
        except Exception as e:
            logger.exception(f"Job {job_id} failed with exception")
            log_output = f"Worker Error:\n{traceback.format_exc()}"
            status = "ERROR"
        end_ts = time.time()
        duration = end_ts - start_ts
        self.jobs_processed += 1
        logger.info(f"Job {job_id} finished with status {status} in {duration:.2f}s")
        result_msg = {
            "type": "job_result",
            "job_id": job_id,
            "worker_id": WORKER_ID,
            "status": status,
            "log_output": log_output.strip(),
            "run_time": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "duration_seconds": duration,
        }
        await self.send_json(result_msg)


if __name__ == "__main__":
    client = WorkerClient()
    try:
        asyncio.run(client.connect())
    except KeyboardInterrupt:
        logger.exception("Worker stopped by user")