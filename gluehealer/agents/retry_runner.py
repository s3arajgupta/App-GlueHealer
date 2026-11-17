"""
Retry Runner Agent

Executes the patched script and evaluates the result.
Routes to one of three outcomes:
  - healed   → job succeeded, pipeline ends
  - failed   → job still fails, loop back for another attempt
  - escalated → max retries exceeded, alert a human
"""
from ..state import HealerState
from ..tools.interface import JobRunner


def retry_runner(state: HealerState, job_runner: JobRunner) -> dict:
    retry_count = state.get("retry_count", 0) + 1
    max_retries = state.get("max_retries", 3)

    print(
        f"\n🔄 Retry Runner: executing '{state['job_name']}' "
        f"(attempt {retry_count}/{max_retries})..."
    )

    success, stdout, stderr = job_runner.run_job(state["script_path"])

    # Update the most recent patch outcome
    history = list(state.get("historical_patches", []))

    if success:
        print(f"   ✅ Job succeeded!")
        if stdout.strip():
            print(f"   Output:\n{stdout}")

        if history:
            history[-1]["outcome"] = "success"

        return {
            "status": "healed",
            "retry_count": retry_count,
            "run_output": stdout,
            "error_logs": "",
            "historical_patches": history,
        }

    # --- Job failed ---
    if history:
        history[-1]["outcome"] = "failed"

    if retry_count >= max_retries:
        print(
            f"\n🛑 Max retries ({max_retries}) exceeded. "
            "Escalating to human engineer."
        )
        return {
            "status": "escalated",
            "retry_count": retry_count,
            "error_logs": stderr,
            "run_output": stdout,
            "historical_patches": history,
        }

    print(f"   ❌ Job still failing. Will re-analyze.")
    print(f"   New error:\n{stderr}")

    return {
        "status": "failed",
        "retry_count": retry_count,
        "error_logs": stderr,
        "run_output": stdout,
        "historical_patches": history,
    }
