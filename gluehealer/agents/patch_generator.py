"""
Patch Generator Agent

Produces non-destructive code patches (for code bugs) or auto-tuned resource
configurations (for infrastructure bottlenecks such as OOM and timeouts).
"""
import difflib
import re
from ..state import HealerState
from ..config import chat_completion


def _strip_markdown_fences(text: str) -> str:
    """Extract Python code from markdown fences if present, otherwise clean up text."""
    match = re.search(r"```(?:python)?\s*\n(.*?)\n```", text, re.DOTALL)
    if match:
        return match.group(1).strip()

    lines = text.strip().splitlines()
    if lines and lines[0].strip().startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip().startswith("```"):
        lines = lines[:-1]
    return "\n".join(lines).strip()


def _generate_infra_patch(state: HealerState) -> dict:
    """Auto-tune AWS Glue worker memory, worker count, or timeout parameters."""
    current_cfg = state.get("current_job_config") or {
        "WorkerType": "G.1X",
        "NumberOfWorkers": 2,
        "Timeout": 60,
    }

    current_worker = current_cfg.get("WorkerType", "G.1X")
    current_num = current_cfg.get("NumberOfWorkers", 2)
    current_timeout = current_cfg.get("Timeout", 60)

    # Scale worker type: G.1X -> G.2X -> G.4X
    worker_map = {"Standard": "G.1X", "G.1X": "G.2X", "G.2X": "G.4X", "G.4X": "G.8X"}
    new_worker = worker_map.get(current_worker, "G.2X")
    new_num = max(current_num * 2, 4)

    error_str = state.get("error_logs", "").lower()
    new_timeout = current_timeout * 2 if "timeout" in error_str else current_timeout

    proposed_cfg = {
        "WorkerType": new_worker,
        "NumberOfWorkers": new_num,
        "Timeout": new_timeout,
    }

    config_diff = (
        "--- Current AWS Glue Job Configuration\n"
        "+++ Auto-Tuned Resource Configuration\n"
        f"- WorkerType: {current_worker} (16 GB RAM per executor)\n"
        f"+ WorkerType: {new_worker} (32 GB RAM per executor) [2x Memory Ceiling Allocated]\n"
        f"- NumberOfWorkers: {current_num}\n"
        f"+ NumberOfWorkers: {new_num} [Horizontal Partition Parallelism Scaling]\n"
    )
    if new_timeout != current_timeout:
        config_diff += (
            f"- Timeout: {current_timeout} minutes\n"
            f"+ Timeout: {new_timeout} minutes [Extended Execution Window]\n"
        )

    print("   ✅ Infrastructure configuration patch generated (Auto-Tuned G.2X / 4 Workers)")
    return {
        "corrected_script": state.get("script_content", ""),
        "patch_display": config_diff,
        "current_job_config": current_cfg,
        "proposed_job_config": proposed_cfg,
        "status": "patch_ready",
    }


def patch_generator(state: HealerState) -> dict:
    print("🩹 Patch Generator: generating fix...", flush=True)

    # Route infrastructure failures to resource auto-tuning
    if state.get("failure_category") == "infrastructure":
        return _generate_infra_patch(state)

    # --- Code Bug Path ---
    if state.get("demo_mode"):
        corrected = state.get("script_content", "").replace('record["unit_price"]', 'record["price"]')
        if 'record["unit_price"]' not in state.get("script_content", ""):
            corrected = (
                state.get("script_content", "")
                .replace("record['is_active']", "record.get('is_active', True)")
                .replace("sessions = row['sessions']", "sessions = max(row['sessions'], 1)")
            )
        print("   ✅ Code patch generated (demo mode)")
    else:
        raw = chat_completion([
            {
                "role": "system",
                "content": (
                    "You are an expert code repair agent. "
                    "Generate the COMPLETE corrected Python script. "
                    "Output ONLY valid Python code — no markdown fences, "
                    "no explanations, no commentary. "
                    "The output must be directly executable."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Fix this script based on the root cause analysis below.\n\n"
                    f"## Original Script\n```python\n{state.get('script_content', '')}\n```\n\n"
                    f"## Root Cause Analysis\n{state.get('rca_result', '')}\n\n"
                    "Output the complete corrected Python script. "
                    "No markdown, no explanations — just the code."
                ),
            },
        ])
        corrected = _strip_markdown_fences(raw)
        print("   ✅ Code patch generated")

    # Compute unified diff for human review
    orig_lines = state.get("script_content", "").splitlines(keepends=True)
    fix_lines = corrected.splitlines(keepends=True)
    diff = difflib.unified_diff(
        orig_lines,
        fix_lines,
        fromfile="original",
        tofile="patched",
    )
    patch_display = "".join(diff)

    if not patch_display:
        patch_display = "(no visible diff — LLM returned identical code)"

    return {
        "corrected_script": corrected,
        "patch_display": patch_display,
        "status": "patch_ready",
    }
