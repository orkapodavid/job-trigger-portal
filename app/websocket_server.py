from fastapi import WebSocket, WebSocketDisconnect, Request
from fastapi.responses import JSONResponse
from typing import Optional, Any
import datetime
import json
import logging
import asyncio
from sqlmodel import Session, create_engine
from app.models import JobExecutionLog, ScheduledJob, get_db_url

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("WebSocketServer")
connected_workers: dict[str, dict] = {}
connected_sockets: dict[str, WebSocket] = {}
engine = create_engine(get_db_url())


class EventBroadcaster:
    def __init__(self):
        self.subscribers: list[asyncio.Queue] = []

    async def subscribe(self) -> asyncio.Queue:
        queue = asyncio.Queue()
        self.subscribers.append(queue)
        return queue

    async def broadcast(self, message: dict):
        for queue in self.subscribers:
            await queue.put(message)


broadcaster = EventBroadcaster()


def cleanup_stale_workers():
    """Remove workers that haven't sent a heartbeat in 3 minutes."""
    now = datetime.datetime.now(datetime.timezone.utc)
    stale_ids = []
    for wid, data in connected_workers.items():
        try:
            last_seen_str = data.get("last_seen_server")
            if last_seen_str:
                last_seen = datetime.datetime.fromisoformat(last_seen_str)
                if (now - last_seen).total_seconds() > 180:
                    stale_ids.append(wid)
        except Exception as e:
            logger.exception(f"Error cleaning up worker {wid}: {e}")
            stale_ids.append(wid)
    for wid in stale_ids:
        if wid in connected_workers:
            del connected_workers[wid]
        if wid in connected_sockets:
            del connected_sockets[wid]


async def send_to_worker(worker_id: str, message: dict) -> bool:
    """Send a JSON message to a specific worker via WebSocket."""
    if worker_id in connected_sockets:
        try:
            websocket = connected_sockets[worker_id]
            await websocket.send_text(json.dumps(message))
            return True
        except Exception as e:
            logger.exception(f"Failed to send to worker {worker_id}: {e}")
            return False
    return False


def get_available_worker() -> Optional[str]:
    """Select a suitable worker for job execution."""
    if not connected_workers:
        return None
    for wid, data in connected_workers.items():
        if data.get("status") == "idle" and wid in connected_sockets:
            return wid
    for wid in connected_workers:
        if wid in connected_sockets:
            return wid
    return None


async def dispatch_job_to_worker(job_id: int, script_path: str) -> bool:
    """Find a worker and send the execute_job command."""
    worker_id = get_available_worker()
    if not worker_id:
        logger.warning(f"No workers available to dispatch job {job_id}")
        return False
    message = {"type": "execute_job", "job_id": job_id, "script_path": script_path}
    success = await send_to_worker(worker_id, message)
    if success:
        logger.info(f"Dispatched job {job_id} to worker {worker_id}")
        return True
    return False


def handle_job_result(data: dict):
    """Process a job result from a worker and update the database."""
    job_id = data.get("job_id")
    status = data.get("status")
    log_output = data.get("log_output")
    run_time_iso = data.get("run_time")
    if not job_id:
        return
    try:
        run_time = (
            datetime.datetime.fromisoformat(run_time_iso)
            if run_time_iso
            else datetime.datetime.now(datetime.timezone.utc)
        )
    except ValueError as e:
        logger.exception(f"Error parsing run_time: {e}")
        run_time = datetime.datetime.now(datetime.timezone.utc)
    try:
        with Session(engine) as session:
            log_entry = JobExecutionLog(
                job_id=job_id,
                run_time=run_time,
                status=status or "UNKNOWN",
                log_output=log_output or "",
            )
            session.add(log_entry)
            session.commit()
            logger.info(f"Recorded execution result for job {job_id}: {status}")
    except Exception as e:
        logger.exception(f"Error saving job result for job {job_id}: {e}")


async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    worker_id = None
    try:
        while True:
            data_json = await websocket.receive_text()
            try:
                data = json.loads(data_json)
                msg_type = data.get("type")
                w_id = data.get("worker_id")
                if w_id:
                    worker_id = w_id
                    if (
                        worker_id not in connected_sockets
                        or connected_sockets[worker_id] != websocket
                    ):
                        connected_sockets[worker_id] = websocket
                if msg_type == "worker_register":
                    data["last_seen_server"] = datetime.datetime.now(
                        datetime.timezone.utc
                    ).isoformat()
                    connected_workers[worker_id] = data
                    await websocket.send_text(
                        json.dumps({"type": "ack", "msg": "registered"})
                    )
                    logger.info(f"Worker registered: {worker_id}")
                elif msg_type == "heartbeat":
                    if worker_id:
                        data["last_seen_server"] = datetime.datetime.now(
                            datetime.timezone.utc
                        ).isoformat()
                        connected_workers[worker_id] = data
                        await websocket.send_text(
                            json.dumps({"type": "ack", "received": True})
                        )
                        cleanup_stale_workers()
                        await broadcaster.broadcast(data)
                elif msg_type == "job_result":
                    handle_job_result(data)
                    await broadcaster.broadcast(
                        {
                            "type": "event",
                            "event": "job_completed",
                            "job_id": data.get("job_id"),
                            "status": data.get("status"),
                            "worker_id": worker_id,
                        }
                    )
                elif msg_type == "event":
                    await broadcaster.broadcast(data)
            except json.JSONDecodeError:
                logger.exception("Invalid JSON received")
            except Exception as e:
                logger.exception(f"Error processing message: {e}")
    except WebSocketDisconnect as e:
        logger.exception(f"WebSocket disconnected: {e}")
        logger.info(f"Worker disconnected: {worker_id}")
        if worker_id:
            if worker_id in connected_sockets:
                del connected_sockets[worker_id]
    except Exception as e:
        logger.exception(f"WebSocket error: {e}")
        if worker_id and worker_id in connected_sockets:
            del connected_sockets[worker_id]


async def get_worker_status(request: Request):
    cleanup_stale_workers()
    return JSONResponse(connected_workers)
