"""
GlueHealer CLI entrypoint.

Usage:
    python -m gluehealer <script>                     # heal a broken script
    python -m gluehealer <script> --max-retries 5     # custom retry limit
    python -m gluehealer <script> --job-name my-job   # custom job name
"""
import argparse
import os
import sys

from .config import MAX_RETRIES
from .graph import build_graph
from .tools.local import LocalJobRunner


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="gluehealer",
        description="GlueHealer — self-healing agent for failed ETL jobs",
    )
    parser.add_argument("script", help="Path to the Python script to heal")
    parser.add_argument(
        "--max-retries",
        type=int,
        default=MAX_RETRIES,
        help=f"Maximum healing attempts (default: {MAX_RETRIES})",
    )
    parser.add_argument(
        "--job-name",
        help="Job name (defaults to the script filename without extension)",
    )
    parser.add_argument(
        "--auto-approve",
        action="store_true",
        help="Automatically approve patches without human confirmation prompt",
    )
    args = parser.parse_args()

    script_path = os.path.abspath(args.script)
    job_name = args.job_name or os.path.splitext(os.path.basename(script_path))[0]

    if not os.path.exists(script_path):
        print(f"❌ Script not found: {script_path}")
        sys.exit(1)

    # ── Step 1: Run the job to see if it actually fails ────────────
    print(f"🔍 Running job '{job_name}' to check for failures...")
    print(f"   Script: {script_path}")
    print()

    runner = LocalJobRunner()
    success, stdout, stderr = runner.run_job(script_path)

    if success:
        print(f"✅ Job '{job_name}' ran successfully — nothing to heal!")
        if stdout.strip():
            print(f"Output:\n{stdout}")
        return

    print(f"❌ Job '{job_name}' failed. Starting healing pipeline...\n")
    print(f"Error:\n{stderr}")

    # ── Step 2: Build and invoke the healing graph ─────────────────
    graph = build_graph()

    initial_state = {
        "job_name": job_name,
        "script_path": script_path,
        "original_script_path": script_path,
        "script_content": "",
        "error_logs": stderr,
        "historical_patches": [],
        "rca_result": "",
        "corrected_script": "",
        "patch_display": "",
        "human_feedback": "",
        "patched_script_path": "",
        "retry_count": 0,
        "max_retries": args.max_retries,
        "auto_approve": args.auto_approve,
        "status": "failed",
        "run_output": "",
    }

    final_state = graph.invoke(initial_state)

    # ── Step 3: Summary ────────────────────────────────────────────
    print()
    print("=" * 70)
    if final_state["status"] == "healed":
        print("🎉 JOB HEALED SUCCESSFULLY")
        print(f"   Attempts needed:  {final_state['retry_count']}")
        print(f"   Patches applied:  {len(final_state['historical_patches'])}")
        print(f"   Healed script:    {final_state['patched_script_path']}")
        print(f"   Original script:  {final_state['original_script_path']} (unchanged)")
    elif final_state["status"] == "escalated":
        print("🛑 HEALING FAILED — ESCALATE TO HUMAN ENGINEER")
        print(f"   Attempts made:    {final_state['retry_count']}")
        print(f"   Patches tried:    {len(final_state['historical_patches'])}")
        print(f"   Last error:")
        print(f"   {final_state['error_logs'][:300]}")
    else:
        print(f"⚠️  Pipeline ended with status: {final_state['status']}")
    print("=" * 70)


if __name__ == "__main__":
    main()
