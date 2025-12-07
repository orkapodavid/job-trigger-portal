import reflex as rx
from app.state import State
from app.models import ScheduledJob, JobExecutionLog


def format_datetime(date_val: rx.Var) -> rx.Component:
    """Format a datetime value to a readable string using rx.moment."""
    return rx.moment(date_val, format="YYYY-MM-DD HH:mm")


def format_interval(job: dict) -> rx.Component:
    """Display the pre-calculated formatted interval string."""
    return rx.el.span(job["formatted_interval"])


def status_indicator(is_active: bool) -> rx.Component:
    return rx.el.div(
        rx.cond(
            is_active,
            rx.el.span(
                rx.el.span(class_name="w-1.5 h-1.5 rounded-full bg-emerald-500 mr-1.5"),
                "Active",
                class_name="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-emerald-50 text-emerald-700 border border-emerald-100",
            ),
            rx.el.span(
                rx.el.span(class_name="w-1.5 h-1.5 rounded-full bg-slate-400 mr-1.5"),
                "Inactive",
                class_name="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-slate-50 text-slate-600 border border-slate-200",
            ),
        )
    )


def log_status_badge(status: str) -> rx.Component:
    return rx.el.span(
        status,
        class_name=rx.match(
            status,
            (
                "SUCCESS",
                "inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800",
            ),
            (
                "FAILURE",
                "inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-800",
            ),
            (
                "RUNNING",
                "inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800",
            ),
            (
                "ERROR",
                "inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-orange-100 text-orange-800",
            ),
            "inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-800",
        ),
    )


def create_job_modal() -> rx.Component:
    return rx.radix.primitives.dialog.root(
        rx.radix.primitives.dialog.trigger(
            rx.el.button(
                rx.icon("plus", class_name="h-4 w-4 mr-2"),
                "New Job",
                class_name="flex items-center bg-violet-600 text-white px-4 py-2 rounded-lg hover:bg-violet-700 transition-colors shadow-sm text-sm font-medium",
            )
        ),
        rx.radix.primitives.dialog.portal(
            rx.radix.primitives.dialog.overlay(
                class_name="fixed inset-0 bg-black/50 backdrop-blur-sm z-40"
            ),
            rx.radix.primitives.dialog.content(
                rx.radix.primitives.dialog.title(
                    "Create New Scheduled Job",
                    class_name="text-xl font-semibold text-gray-900 mb-1",
                ),
                rx.radix.primitives.dialog.description(
                    "Configure a new job to run automatically.",
                    class_name="text-sm text-gray-500 mb-6",
                ),
                rx.el.div(
                    rx.el.label(
                        "Job Name",
                        class_name="block text-sm font-medium text-gray-700 mb-1",
                    ),
                    rx.el.input(
                        on_change=State.set_new_job_name,
                        placeholder="e.g., Daily Backup",
                        class_name="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-violet-500 focus:border-transparent",
                        default_value=State.new_job_name,
                    ),
                    class_name="mb-4",
                ),
                rx.el.div(
                    rx.el.label(
                        "Script Path",
                        class_name="block text-sm font-medium text-gray-700 mb-1",
                    ),
                    rx.el.input(
                        on_change=State.set_new_job_script_path,
                        placeholder="/path/to/script.py",
                        class_name="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-violet-500 focus:border-transparent",
                        default_value=State.new_job_script_path,
                    ),
                    class_name="mb-4",
                ),
                rx.el.div(
                    rx.el.label(
                        "Run Every",
                        class_name="block text-sm font-medium text-gray-700 mb-1",
                    ),
                    rx.el.div(
                        rx.el.input(
                            on_change=State.set_new_job_interval_value,
                            type="number",
                            min="1",
                            placeholder="1",
                            class_name="flex-1 rounded-l-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-violet-500 focus:border-transparent focus:z-10",
                            default_value=State.new_job_interval_value,
                        ),
                        rx.el.select(
                            rx.el.option("Seconds", value="Seconds"),
                            rx.el.option("Minutes", value="Minutes"),
                            rx.el.option("Hours", value="Hours"),
                            rx.el.option("Days", value="Days"),
                            value=State.new_job_interval_unit,
                            on_change=State.set_new_job_interval_unit,
                            class_name="w-32 rounded-r-md border-l-0 border border-gray-300 px-3 py-2 text-sm bg-gray-50 focus:outline-none focus:ring-2 focus:ring-violet-500 focus:border-transparent focus:z-10",
                        ),
                        class_name="flex rounded-md shadow-sm",
                    ),
                    class_name="mb-6",
                ),
                rx.el.div(
                    rx.radix.primitives.dialog.close(
                        rx.el.button(
                            "Cancel",
                            class_name="px-4 py-2 border border-gray-300 rounded-lg text-sm font-medium text-gray-700 hover:bg-gray-50 transition-colors",
                        )
                    ),
                    rx.el.button(
                        "Create Job",
                        on_click=State.add_job,
                        class_name="px-4 py-2 bg-violet-600 text-white rounded-lg text-sm font-medium hover:bg-violet-700 transition-colors",
                    ),
                    class_name="flex justify-end space-x-3",
                ),
                class_name="fixed top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 bg-white rounded-xl shadow-2xl p-6 w-full max-w-lg z-50 focus:outline-none",
            ),
        ),
        open=State.is_modal_open,
        on_open_change=State.set_modal_open,
    )


def job_row(job: dict) -> rx.Component:
    return rx.el.tr(
        rx.el.td(
            rx.el.div(
                rx.el.p(job["name"], class_name="font-medium text-gray-900"),
                class_name="flex items-center",
            ),
            class_name="px-6 py-4 whitespace-nowrap text-sm",
        ),
        rx.el.td(
            rx.el.div(
                rx.el.code(
                    job["script_path"],
                    class_name="bg-gray-100 px-2 py-1 rounded text-xs text-gray-600 font-mono",
                )
            ),
            class_name="px-6 py-4 whitespace-nowrap text-sm",
        ),
        rx.el.td(
            status_indicator(job["is_active"]), class_name="px-6 py-4 whitespace-nowrap"
        ),
        rx.el.td(
            rx.el.span(format_interval(job), class_name="text-gray-500"),
            class_name="px-6 py-4 whitespace-nowrap text-sm",
        ),
        rx.el.td(
            rx.el.span(
                rx.cond(
                    job["next_run"], format_datetime(job["next_run"]), "Not scheduled"
                ),
                class_name="text-gray-500 font-mono text-xs",
            ),
            class_name="px-6 py-4 whitespace-nowrap text-sm",
        ),
        rx.el.td(
            rx.el.div(
                rx.el.button(
                    rx.icon("circle_play", class_name="h-4 w-4 text-violet-600"),
                    on_click=lambda: State.run_job_now(job["id"]),
                    class_name="p-1.5 hover:bg-violet-50 rounded-md transition-colors disabled:opacity-50 disabled:cursor-not-allowed",
                    title="Run Now",
                ),
                rx.el.button(
                    rx.cond(
                        job["is_active"],
                        rx.icon("pause", class_name="h-4 w-4 text-amber-600"),
                        rx.icon("play", class_name="h-4 w-4 text-emerald-600"),
                    ),
                    on_click=lambda: State.toggle_job_status(job["id"]),
                    class_name="p-1.5 hover:bg-gray-100 rounded-md transition-colors",
                    title=rx.cond(job["is_active"], "Pause Job", "Activate Job"),
                ),
                rx.el.button(
                    rx.icon("trash-2", class_name="h-4 w-4 text-red-600"),
                    on_click=lambda: State.delete_job(job["id"]),
                    class_name="p-1.5 hover:bg-red-50 rounded-md transition-colors",
                    title="Delete Job",
                ),
                class_name="flex items-center space-x-1",
            ),
            class_name="px-6 py-4 whitespace-nowrap text-right text-sm font-medium",
        ),
        class_name=rx.cond(
            State.selected_job_id == job["id"],
            "bg-violet-50 hover:bg-violet-100 cursor-pointer transition-colors",
            "hover:bg-gray-50 cursor-pointer transition-colors border-b border-gray-100 last:border-0",
        ),
        on_click=lambda: State.select_job(job["id"]),
    )


def jobs_table() -> rx.Component:
    return rx.el.div(
        rx.el.div(
            rx.el.div(
                rx.el.h2(
                    "Scheduled Jobs", class_name="text-lg font-semibold text-gray-900"
                ),
                rx.el.p(
                    "Manage your automated tasks", class_name="text-sm text-gray-500"
                ),
                class_name="flex flex-col",
            ),
            rx.el.div(
                rx.el.div(
                    rx.icon(
                        "search",
                        class_name="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400",
                    ),
                    rx.el.input(
                        placeholder="Search jobs...",
                        on_change=State.set_search_query,
                        class_name="pl-9 pr-4 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-violet-500 focus:border-transparent w-64",
                        default_value=State.search_query,
                    ),
                    class_name="relative",
                ),
                create_job_modal(),
                class_name="flex items-center gap-3",
            ),
            class_name="flex justify-between items-center mb-6",
        ),
        rx.el.div(
            rx.el.table(
                rx.el.thead(
                    rx.el.tr(
                        rx.el.th(
                            "Job Name",
                            class_name="px-6 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider",
                        ),
                        rx.el.th(
                            "Script",
                            class_name="px-6 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider",
                        ),
                        rx.el.th(
                            "Status",
                            class_name="px-6 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider",
                        ),
                        rx.el.th(
                            "Interval",
                            class_name="px-6 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider",
                        ),
                        rx.el.th(
                            "Next Run",
                            class_name="px-6 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider",
                        ),
                        rx.el.th(
                            "Actions",
                            class_name="px-6 py-3 text-right text-xs font-semibold text-gray-500 uppercase tracking-wider",
                        ),
                        class_name="bg-gray-50 border-b border-gray-200",
                    )
                ),
                rx.el.tbody(
                    rx.cond(
                        State.jobs.length() > 0,
                        rx.foreach(State.jobs, lambda job: job_row(job)),
                        rx.el.tr(
                            rx.el.td(
                                rx.el.div(
                                    rx.icon(
                                        "calendar-off",
                                        class_name="h-8 w-8 text-gray-300 mb-2",
                                    ),
                                    rx.el.p(
                                        "No scheduled jobs found",
                                        class_name="text-gray-500 font-medium",
                                    ),
                                    rx.el.p(
                                        "Create a new job to get started",
                                        class_name="text-gray-400 text-sm",
                                    ),
                                    class_name="flex flex-col items-center justify-center py-12",
                                ),
                                col_span=6,
                                class_name="px-6 py-4 text-center",
                            )
                        ),
                    ),
                    class_name="divide-y divide-gray-100 bg-white",
                ),
                class_name="min-w-full",
            ),
            class_name="overflow-x-auto rounded-xl border border-gray-200 bg-white shadow-sm",
        ),
        class_name="flex flex-col h-full",
    )


def log_detail_view() -> rx.Component:
    return rx.el.div(
        rx.el.div(
            rx.el.div(
                rx.el.h3(
                    "Log Details",
                    class_name="text-sm font-semibold text-gray-900 uppercase tracking-wide",
                ),
                rx.el.button(
                    rx.icon("x", class_name="h-4 w-4"),
                    on_click=lambda: State.select_log(-1),
                    class_name="text-gray-400 hover:text-gray-600",
                ),
                class_name="flex justify-between items-center mb-3",
            ),
            rx.el.div(
                rx.el.div(
                    rx.el.span(
                        "Status:", class_name="text-xs font-medium text-gray-500 mr-2"
                    ),
                    log_status_badge(State.selected_log_entry.status),
                    class_name="mb-2 flex items-center",
                ),
                rx.el.div(
                    rx.el.span(
                        "Executed at:",
                        class_name="text-xs font-medium text-gray-500 mr-2",
                    ),
                    rx.el.span(
                        State.selected_log_entry.run_time.to_string(),
                        class_name="text-sm text-gray-800",
                    ),
                    class_name="mb-4 flex items-center",
                ),
                rx.el.div(
                    rx.el.span(
                        "Output:",
                        class_name="text-xs font-medium text-gray-500 mb-1 block",
                    ),
                    rx.el.pre(
                        rx.el.code(
                            State.selected_log_entry.log_output,
                            class_name="text-xs font-mono text-gray-300",
                        ),
                        class_name="bg-gray-900 rounded-lg p-4 overflow-x-auto max-h-96 custom-scrollbar",
                    ),
                    class_name="w-full",
                ),
                class_name="bg-white p-4 rounded-lg border border-gray-200 shadow-sm",
            ),
            class_name="mt-4 animate-in fade-in slide-in-from-top-2 duration-200",
        ),
        class_name="w-full",
    )


def log_item(log: JobExecutionLog) -> rx.Component:
    is_selected = State.selected_log_entry.id == log.id
    return rx.el.div(
        rx.el.div(
            log_status_badge(log.status),
            rx.el.span(log.run_time.to_string(), class_name="text-xs text-gray-500"),
            class_name="flex justify-between items-center w-full mb-1",
        ),
        rx.el.div(
            rx.el.span("ID: ", class_name="text-xs text-gray-400"),
            rx.el.span(log.id, class_name="text-xs text-gray-600 font-mono"),
            class_name="flex items-center",
        ),
        class_name=rx.cond(
            is_selected,
            "p-3 rounded-lg border border-violet-200 bg-violet-50 cursor-pointer transition-all duration-200 shadow-sm",
            "p-3 rounded-lg border border-gray-100 bg-white hover:border-gray-300 cursor-pointer transition-all duration-200",
        ),
        on_click=lambda: State.select_log(log.id),
    )


def execution_logs_panel() -> rx.Component:
    return rx.el.div(
        rx.el.div(
            rx.el.div(
                rx.icon("activity", class_name="h-5 w-5 text-violet-600 mr-2"),
                rx.el.h2(
                    rx.cond(
                        State.selected_job_name,
                        State.selected_job_name,
                        "Execution Logs",
                    ),
                    class_name="text-lg font-semibold text-gray-900 truncate",
                ),
                class_name="flex items-center",
            ),
            rx.el.p(
                rx.cond(
                    State.selected_job_name,
                    "View past execution results",
                    "Select a job to view details",
                ),
                class_name="text-xs text-gray-500 mt-1 ml-7",
            ),
            class_name="mb-6 pb-6 border-b border-gray-100",
        ),
        rx.cond(
            State.selected_job_id,
            rx.el.div(
                rx.cond(
                    State.logs,
                    rx.el.div(
                        rx.el.div(
                            rx.el.h3(
                                "Recent Executions",
                                class_name="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3",
                            ),
                            rx.el.div(
                                rx.foreach(State.logs, log_item),
                                class_name="space-y-2 overflow-y-auto custom-scrollbar pr-1 max-h-[calc(100vh-350px)]",
                            ),
                            class_name="flex flex-col flex-1 min-h-0",
                        ),
                        rx.cond(State.selected_log_entry, log_detail_view()),
                        class_name="flex flex-col gap-6 h-full",
                    ),
                    rx.el.div(
                        rx.el.div(
                            rx.icon("clock", class_name="h-10 w-10 text-gray-200 mb-3"),
                            rx.el.p(
                                "No execution history yet.",
                                class_name="text-sm text-gray-600 font-medium",
                            ),
                            rx.el.p(
                                "Run the job to generate logs.",
                                class_name="text-xs text-gray-400 mt-1",
                            ),
                            class_name="flex flex-col items-center justify-center py-16 bg-gray-50/50 rounded-xl border border-dashed border-gray-200",
                        )
                    ),
                ),
                class_name="flex flex-col h-full overflow-hidden",
            ),
            rx.el.div(
                rx.el.div(
                    rx.icon(
                        "mouse-pointer-2", class_name="h-10 w-10 text-gray-200 mb-3"
                    ),
                    rx.el.p(
                        "Select a job to view logs.",
                        class_name="text-sm text-gray-600 font-medium",
                    ),
                    class_name="flex flex-col items-center justify-center py-16 bg-gray-50/50 rounded-xl border border-dashed border-gray-200",
                ),
                class_name="flex flex-col h-full",
            ),
        ),
        class_name="bg-white border-l border-gray-200 p-6 h-full min-h-screen w-96 flex-shrink-0 flex flex-col shadow-[rgba(0,0,0,0.05)_-4px_0px_16px] z-10",
    )


def dashboard() -> rx.Component:
    return rx.el.div(
        rx.el.div(jobs_table(), class_name="flex-1 p-8 overflow-y-auto"),
        execution_logs_panel(),
        class_name="flex h-screen bg-gray-50 w-full overflow-hidden font-['Inter']",
    )