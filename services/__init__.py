"""
Standalone services for job scheduling and execution.

This package contains independent services that run separately from the Reflex web portal:
- scheduler_service: Discovers due jobs and creates dispatch records
- worker_service: Claims and executes job dispatches
"""
