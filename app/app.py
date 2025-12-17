import reflex as rx
from app.job_manager import dashboard
from app.state import State


def index() -> rx.Component:
    return dashboard()


app = rx.App(
    theme=rx.theme(appearance="light"),
    head_components=[
        rx.el.link(
            href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap",
            rel="stylesheet",
        )
    ],
)
app.add_page(index, route="/", on_load=State.on_load)
