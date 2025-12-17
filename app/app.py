import reflex as rx
import asyncio
from fastapi import FastAPI
from app.job_manager import dashboard
from app.state import State
from app.websocket_server import websocket_endpoint, get_worker_status
from app.scheduler import run_scheduler


def index() -> rx.Component:
    return dashboard()


def api_routes(api: FastAPI):
    api.add_websocket_route("/ws/heartbeat", websocket_endpoint)
    api.add_route("/api/worker-status", get_worker_status, methods=["GET"])

    @api.on_event("startup")
    async def startup_event():
        asyncio.create_task(run_scheduler())

    return api


app = rx.App(
    theme=rx.theme(appearance="light"),
    head_components=[
        rx.el.link(
            href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap",
            rel="stylesheet",
        )
    ],
    api_transformer=api_routes,
)
app.add_page(index, route="/", on_load=State.on_load)
