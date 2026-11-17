"""
GlueHealer shared state schema.

This TypedDict defines the state that flows through the LangGraph workflow.
LangGraph merges partial updates returned by each node into the full state.
"""
from typing import TypedDict


class HealerState(TypedDict, total=False):
    # Job identity
    job_name: str
    script_path: str              # Current path (may change after patching)
    original_script_path: str     # Original path (never changes)

    # Context gathered by Context Builder
    script_content: str
    error_logs: str
    historical_patches: list      # List of {"patch_summary", "outcome", "feedback", "version"}

    # RCA output
    rca_result: str
    failure_category: str         # "code" | "infrastructure"

    # Patch Generator output
    corrected_script: str
    patch_display: str            # Unified diff or config diff for human review
    current_job_config: dict      # e.g. {"WorkerType": "G.1X", "NumberOfWorkers": 2}
    proposed_job_config: dict     # e.g. {"WorkerType": "G.2X", "NumberOfWorkers": 4}

    # Human Approval
    human_feedback: str
    auto_approve: bool
    demo_mode: bool
    status: str                   # failed | analyzing | patch_ready | approved | rejected | applied | healed | escalated

    # Apply Patch
    patched_script_path: str

    # Retry Runner
    retry_count: int
    max_retries: int
    run_output: str
