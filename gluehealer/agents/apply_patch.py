"""
Apply Patch Agent

Creates a versioned copy of the corrected script and updates the
active script_path so the Retry Runner executes the patched version.
The original file is never overwritten — all patches go into job_versions/.
"""
from ..state import HealerState
from ..tools.interface import ScriptStore


def apply_patch(state: HealerState, script_store: ScriptStore) -> dict:
    version = len(state.get("historical_patches", [])) + 1

    # Save versioned copy
    patched_path = script_store.create_version(
        state["job_name"],
        state["corrected_script"],
        version,
        original_path=state.get("original_script_path"),
    )

    # Record this patch in history
    history = list(state.get("historical_patches", []))
    history.append(
        {
            "patch_summary": state["patch_display"][:300],
            "outcome": "applied",  # will be updated to success/failed by retry_runner
            "feedback": state.get("human_feedback", ""),
            "version": version,
        }
    )

    print(f"\n📦 Apply Patch: versioned copy → {patched_path}")

    return {
        "script_path": patched_path,       # Retry Runner will execute this
        "patched_script_path": patched_path,
        "historical_patches": history,
        "status": "applied",
    }
