import reflex as rx
from app.state import State
from app.models import ScheduledJob, JobExecutionLog


def format_datetime(date_val: rx.Var) -> rx.Component:
    """Format a datetime value to a readable string using rx.moment."""
    return rx.moment(date_val, format="YYYY-MM-DD HH:mm", tz="Asia/Hong_Kong")


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
                        "Select Script",
                        class_name="block text-sm font-medium text-gray-700 mb-1",
                    ),
                    rx.el.select(
                        rx.el.option(
                            "Select a script...", value="", disabled=True, selected=True
                        ),
                        rx.foreach(
                            State.available_scripts, lambda s: rx.el.option(s, value=s)
                        ),
                        on_change=State.set_new_job_script_path,
                        value=State.new_job_script_path,
                        class_name="w-full rounded-md border border-gray-300 px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-violet-500 focus:border-transparent",
                    ),
                    class_name="mb-4",
                ),
                rx.el.div(
                    rx.el.label(
                        "Script Arguments (Optional)",
                        class_name="block text-sm font-medium text-gray-700 mb-1",
                    ),
                    rx.el.input(
                        on_change=State.set_new_job_script_args,
                        placeholder="--arg1 value1 --flag",
                        class_name="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-violet-500 focus:border-transparent",
                        default_value=State.new_job_script_args,
                    ),
                    class_name="mb-4",
                ),
                rx.el.div(
                    rx.el.label(
                        "Schedule Type",
                        class_name="block text-sm font-medium text-gray-700 mb-1",
                    ),
                    rx.el.select(
                        rx.el.option("Interval (Simple)", value="interval"),
                        rx.el.option("Hourly", value="hourly"),
                        rx.el.option("Daily", value="daily"),
                        rx.el.option("Weekly", value="weekly"),
                        rx.el.option("Monthly", value="monthly"),
                        rx.el.option("Manual (Run on Demand)", value="manual"),
                        value=State.new_job_schedule_type,
                        on_change=State.set_new_job_schedule_type,
                        class_name="w-full rounded-md border border-gray-300 px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-violet-500 focus:border-transparent",
                    ),
                    class_name="mb-4",
                ),
                rx.el.div(
                    rx.match(
                        State.new_job_schedule_type,
                        (
                            "interval",
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
                            ),
                        ),
                        (
                            "hourly",
                            rx.el.div(
                                rx.el.label(
                                    "Run at Minute (0-59)",
                                    class_name="block text-sm font-medium text-gray-700 mb-1",
                                ),
                                rx.el.input(
                                    type="number",
                                    min="0",
                                    max="59",
                                    on_change=State.set_new_job_schedule_minute,
                                    class_name="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-violet-500 focus:border-transparent",
                                    default_value=State.new_job_schedule_minute,
                                ),
                            ),
                        ),
                        (
                            "daily",
                            rx.el.div(
                                rx.el.label(
                                    "Time (HKT)",
                                    class_name="block text-sm font-medium text-gray-700 mb-1",
                                ),
                                rx.el.input(
                                    type="time",
                                    on_change=State.set_new_job_schedule_time,
                                    class_name="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-violet-500 focus:border-transparent",
                                    default_value=State.new_job_schedule_time,
                                ),
                            ),
                        ),
                        (
                            "weekly",
                            rx.el.div(
                                rx.el.div(
                                    rx.el.div(
                                        rx.el.label(
                                            "Day of Week (HKT)",
                                            class_name="block text-sm font-medium text-gray-700 mb-1",
                                        ),
                                        rx.el.select(
                                            rx.el.option("Monday", value="0"),
                                            rx.el.option("Tuesday", value="1"),
                                            rx.el.option("Wednesday", value="2"),
                                            rx.el.option("Thursday", value="3"),
                                            rx.el.option("Friday", value="4"),
                                            rx.el.option("Saturday", value="5"),
                                            rx.el.option("Sunday", value="6"),
                                            value=State.new_job_schedule_day,
                                            on_change=State.set_new_job_schedule_day,
                                            class_name="w-full rounded-md border border-gray-300 px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-violet-500 focus:border-transparent",
                                        ),
                                    ),
                                    rx.el.div(
                                        rx.el.label(
                                            "Time (HKT)",
                                            class_name="block text-sm font-medium text-gray-700 mb-1",
                                        ),
                                        rx.el.input(
                                            type="time",
                                            on_change=State.set_new_job_schedule_time,
                                            class_name="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-violet-500 focus:border-transparent",
                                            default_value=State.new_job_schedule_time,
                                        ),
                                    ),
                                    class_name="grid grid-cols-2 gap-4",
                                )
                            ),
                        ),
                        (
                            "monthly",
                            rx.el.div(
                                rx.el.div(
                                    rx.el.div(
                                        rx.el.label(
                                            "Day of Month (HKT)",
                                            class_name="block text-sm font-medium text-gray-700 mb-1",
                                        ),
                                        rx.el.input(
                                            type="number",
                                            min="1",
                                            max="31",
                                            on_change=State.set_new_job_schedule_day,
                                            class_name="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-violet-500 focus:border-transparent",
                                            default_value=State.new_job_schedule_day,
                                        ),
                                    ),
                                    rx.el.div(
                                        rx.el.label(
                                            "Time (HKT)",
                                            class_name="block text-sm font-medium text-gray-700 mb-1",
                                        ),
                                        rx.el.input(
                                            type="time",
                                            on_change=State.set_new_job_schedule_time,
                                            class_name="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-violet-500 focus:border-transparent",
                                            default_value=State.new_job_schedule_time,
                                        ),
                                    ),
                                    class_name="grid grid-cols-2 gap-4",
                                )
                            ),
                        ),
                        (
                            "manual",
                            rx.el.div(
                                rx.el.p(
                                    "This job will only run when manually triggered.",
                                    class_name="text-sm text-gray-500 italic",
                                ),
                                class_name="py-2",
                            ),
                        ),
                        rx.el.div(),
                    ),
                    class_name="mb-6 min-h-[80px]",
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
    is_queued = State.running_job_ids.contains(job["id"])
    is_executing = State.processing_job_ids.contains(job["id"])
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
                    class_name="bg-gray-100 px-2 py-1 rounded text-xs text-gray-600 font-mono block mb-1",
                ),
                rx.cond(
                    job["script_args"],
                    rx.el.code(
                        job["script_args"],
                        class_name="bg-violet-50 text-violet-600 px-2 py-0.5 rounded text-[10px] font-mono border border-violet-100",
                    ),
                ),
                class_name="flex flex-col items-start",
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
            rx.el.div(
                rx.cond(
                    is_executing,
                    rx.el.span(
                        rx.el.span(
                            class_name="w-1.5 h-1.5 rounded-full bg-violet-500 mr-1.5 animate-ping absolute inline-flex opacity-75"
                        ),
                        rx.el.span(
                            class_name="relative inline-flex rounded-full h-1.5 w-1.5 bg-violet-500 mr-1.5"
                        ),
                        "Running",
                        class_name="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-violet-50 text-violet-700 border border-violet-100",
                    ),
                    rx.cond(
                        is_queued,
                        rx.el.span(
                            rx.el.span(
                                class_name="w-1.5 h-1.5 rounded-full bg-blue-500 mr-1.5 animate-pulse"
                            ),
                            "Queued",
                            class_name="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-blue-50 text-blue-700 border border-blue-100 animate-pulse",
                        ),
                        rx.el.span(
                            rx.cond(
                                job["next_run"],
                                format_datetime(job["next_run"]),
                                rx.cond(
                                    job["schedule_type"] == "manual",
                                    "Manual / Not Scheduled",
                                    "Not scheduled",
                                ),
                            ),
                            class_name="text-gray-500 font-mono text-xs",
                        ),
                    ),
                ),
                rx.cond(
                    is_executing,
                    rx.el.p(
                        "Executing on worker...",
                        class_name="text-[10px] text-violet-500 mt-0.5 italic",
                    ),
                    rx.cond(
                        is_queued,
                        rx.el.p(
                            "Pending dispatch...",
                            class_name="text-[10px] text-blue-500 mt-0.5 italic",
                        ),
                    ),
                ),
            ),
            class_name="px-6 py-4 whitespace-nowrap text-sm",
        ),
        rx.el.td(
            rx.el.div(
                rx.el.button(
                    rx.cond(
                        is_queued | is_executing,
                        rx.spinner(size="1", class_name="text-violet-600"),
                        rx.icon("circle_play", class_name="h-4 w-4 text-violet-600"),
                    ),
                    on_click=lambda: State.run_job_now(job["id"]),
                    class_name="p-1.5 hover:bg-violet-50 rounded-md transition-colors disabled:opacity-50 disabled:cursor-not-allowed",
                    title="Run Now",
                    disabled=is_queued | is_executing,
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


def worker_status_widget() -> rx.Component:
    return rx.el.div(
        rx.el.div(
            rx.el.div(
                class_name=rx.match(
                    State.worker_status,
                    ("online", "h-2.5 w-2.5 rounded-full bg-emerald-500 animate-pulse"),
                    ("stale", "h-2.5 w-2.5 rounded-full bg-amber-400"),
                    ("offline", "h-2.5 w-2.5 rounded-full bg-rose-500"),
                    "h-2.5 w-2.5 rounded-full bg-slate-300",
                )
            ),
            rx.el.span(
                rx.match(
                    State.worker_status,
                    (
                        "online",
                        rx.cond(
                            State.active_workers_count > 1,
                            f"System Online ({State.active_workers_count})",
                            "System Online",
                        ),
                    ),
                    ("stale", "System Stale"),
                    ("offline", "System Offline"),
                    "Connecting...",
                ),
                class_name="text-xs font-semibold ml-2",
            ),
            class_name=rx.match(
                State.worker_status,
                (
                    "online",
                    "flex items-center px-3 py-1.5 rounded-full border border-emerald-200 bg-emerald-50 text-emerald-700 shadow-sm transition-all",
                ),
                (
                    "stale",
                    "flex items-center px-3 py-1.5 rounded-full border border-amber-200 bg-amber-50 text-amber-700 shadow-sm transition-all",
                ),
                (
                    "offline",
                    "flex items-center px-3 py-1.5 rounded-full border border-rose-200 bg-rose-50 text-rose-700 shadow-sm transition-all",
                ),
                "flex items-center px-3 py-1.5 rounded-full border border-slate-200 bg-slate-50 text-slate-600 shadow-sm transition-all",
            ),
        ),
        rx.el.div(
            rx.el.div(
                rx.el.div(
                    rx.el.p(
                        "Worker ID",
                        class_name="text-[10px] uppercase text-gray-400 font-bold tracking-wider mb-0.5",
                    ),
                    rx.el.p(
                        State.worker_id,
                        class_name="text-xs font-mono text-gray-700 truncate",
                    ),
                    class_name="mb-3",
                ),
                rx.el.div(
                    rx.el.p(
                        "Uptime",
                        class_name="text-[10px] uppercase text-gray-400 font-bold tracking-wider mb-0.5",
                    ),
                    rx.el.p(
                        State.worker_uptime_str,
                        class_name="text-xs font-medium text-gray-700",
                    ),
                    class_name="mb-3",
                ),
                rx.el.div(
                    rx.el.p(
                        "Last Heartbeat",
                        class_name="text-[10px] uppercase text-gray-400 font-bold tracking-wider mb-0.5",
                    ),
                    rx.moment(
                        State.last_heartbeat,
                        from_now=True,
                        class_name="text-xs font-medium text-gray-700",
                    ),
                    class_name="mb-3",
                ),
                rx.el.div(
                    rx.el.p(
                        "Processed Jobs",
                        class_name="text-[10px] uppercase text-gray-400 font-bold tracking-wider mb-0.5",
                    ),
                    rx.el.p(
                        State.jobs_processed_count,
                        class_name="text-xs font-medium text-gray-700",
                    ),
                ),
                class_name="p-4 bg-white border border-gray-100 shadow-xl rounded-xl w-56 backdrop-blur-sm",
            ),
            class_name="absolute top-full right-0 mt-2 opacity-0 group-hover:opacity-100 transition-all duration-200 transform origin-top-right scale-95 group-hover:scale-100 z-50 pointer-events-none group-hover:pointer-events-auto",
        ),
        class_name="relative group cursor-help z-20",
    )


def jobs_table() -> rx.Component:
    return rx.el.div(
        rx.el.div(
            rx.el.div(
                rx.el.h2(
                    "Scheduled Jobs", class_name="text-lg font-semibold text-gray-900"
                ),
                rx.el.div(
                    rx.el.p(
                        "Manage your automated tasks",
                        class_name="text-sm text-gray-500",
                    ),
                    rx.el.span(
                        "Hong Kong Time (UTC+8)",
                        class_name="ml-2 inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-indigo-100 text-indigo-800",
                    ),
                    class_name="flex items-center",
                ),
                class_name="flex flex-col",
            ),
            rx.el.div(
                worker_status_widget(),
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
                        format_datetime(State.selected_log_entry.run_time),
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
            rx.el.span(
                format_datetime(log.run_time), class_name="text-xs text-gray-500"
            ),
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
                rx.cond(
                    State.selected_job_id,
                    rx.el.button(
                        rx.icon(
                            "refresh-cw",
                            class_name=rx.cond(
                                State.is_loading_logs, "h-4 w-4 animate-spin", "h-4 w-4"
                            ),
                        ),
                        on_click=State.refresh_logs,
                        disabled=State.is_loading_logs,
                        class_name="p-1.5 text-gray-500 hover:text-violet-600 hover:bg-violet-50 rounded-md transition-colors",
                        title="Refresh Logs",
                    ),
                ),
                class_name="flex items-center justify-between",
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
                    State.is_loading_logs,
                    rx.el.div(
                        rx.el.div(
                            class_name="h-12 w-full bg-gray-100 rounded-lg animate-pulse mb-2"
                        ),
                        rx.el.div(
                            class_name="h-12 w-full bg-gray-100 rounded-lg animate-pulse mb-2"
                        ),
                        rx.el.div(
                            class_name="h-12 w-full bg-gray-100 rounded-lg animate-pulse mb-2"
                        ),
                        class_name="flex flex-col w-full",
                    ),
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
                                rx.icon(
                                    "clock", class_name="h-10 w-10 text-gray-200 mb-3"
                                ),
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