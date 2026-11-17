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

    # Patch Generator output
    corrected_script: str
    patch_display: str            # Unified diff for human review

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
