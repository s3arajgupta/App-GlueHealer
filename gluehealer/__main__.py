"""
GlueHealer CLI entrypoint.

Supports dual modes:
  1. Local / Demo mode: Heals scripts locally on filesystem with zero dependencies
  2. AWS Cloud mode: Connects to AWS Glue, CloudWatch Logs, and S3 to heal live cloud ETL jobs
  3. One-Click Rollback: Instant rollback of script pointers and worker configurations

Usage:
    python -m gluehealer demo                         # instant offline showcase demo
    python -m gluehealer sample_jobs/broken_etl.py    # heal local script
    python -m gluehealer --aws --job-name my-glue-job # heal AWS Glue job in the cloud
    python -m gluehealer rollback                     # one-click rollback to original baseline
    python -m gluehealer rollback --to-version v1     # roll back to specific snapshot version
    python -m gluehealer rollback --aws --job-name J  # roll back AWS Glue job configuration
"""
from __future__ import annotations

import argparse
import os
import sys

from .config import MAX_RETRIES, AWS_REGION, AWS_PROFILE
from .graph import build_graph
from .tools.local import LocalJobRunner, LocalScriptStore


def _handle_rollback(args: argparse.Namespace) -> None:
    """Handle the one-click rollback CLI command for local and AWS environments."""
    print("=" * 70)
    print("🔙 GlueHealer One-Click Rollback")
    print("=" * 70)

    if args.aws:
        try:
            from .tools.aws import GlueJobRunner, S3ScriptStore
        except ImportError as e:
            print(f"❌ Failed to import AWS tool suite: {e}")
            print("   Ensure boto3 is installed: pip install boto3")
            sys.exit(1)

        job_name = args.job_name
        if not job_name:
            print("❌ Error: --job-name is required when rolling back an AWS Glue job.")
            print("   Example: python -m gluehealer rollback --aws --job-name my-glue-job --to-s3-path s3://bucket/script.py")
            sys.exit(1)

        region = args.region or AWS_REGION
        profile = args.profile or AWS_PROFILE
        glue_runner = GlueJobRunner(job_name=job_name, region_name=region, profile_name=profile)
        s3_store = S3ScriptStore(default_bucket=args.s3_bucket, region_name=region, profile_name=profile)

        print(f"   Target Glue Job: {job_name}")
        print(f"   AWS Region:      {region}")

        # Fetch current state
        try:
            job_def = glue_runner.get_job_definition()
            current_script = job_def.get("Command", {}).get("ScriptLocation", "unknown")
            current_worker = job_def.get("WorkerType", "Standard")
            current_num = job_def.get("NumberOfWorkers", 2)
            print(f"   Current S3 script:   {current_script}")
            print(f"   Current WorkerType:  {current_worker} ({current_num} workers)")
        except Exception as e:
            print(f"❌ Could not access AWS Glue job '{job_name}': {e}")
            sys.exit(1)

        # Resolve target S3 path
        target_s3 = args.to_s3_path
        if not target_s3:
            # Query S3 version history
            available = s3_store.list_versions(job_name)
            if available:
                print(f"   Found {len(available)} version snapshot(s) in S3:")
                for v in available:
                    print(f"     - {v}")
            if args.to_version and args.to_version != "original":
                # Find matching version
                matched = [v for v in available if f"/{args.to_version}.py" in v or f"/{args.to_version}/" in v]
                target_s3 = matched[0] if matched else None

            if not target_s3:
                print("\n❌ Error: Target S3 script URI not specified.")
                print("   Provide --to-s3-path s3://<bucket>/path/to/script.py to complete rollback.")
                sys.exit(1)

        print(f"\n   Restoring ScriptLocation → {target_s3}")
        if args.restore_worker_type:
            print(f"   Restoring WorkerType     → {args.restore_worker_type}")
        if args.restore_num_workers:
            print(f"   Restoring NumberOfWorkers→ {args.restore_num_workers}")

        try:
            glue_runner.rollback(
                to_script_s3_path=target_s3,
                restore_worker_type=args.restore_worker_type,
                restore_num_workers=args.restore_num_workers,
            )
            print()
            print("✅ AWS Glue Job successfully rolled back!")
            print(f"   Active script is now: {target_s3}")
        except Exception as e:
            print(f"❌ Rollback failed: {e}")
            sys.exit(1)
        print("=" * 70)
        return

    # --- Local Rollback Path ---
    store = LocalScriptStore()
    target_version = args.to_version or "original"

    # Infer job name
    job_name = args.job_name
    target_script = None

    if not job_name:
        if args.script and args.script not in ("rollback", "demo") and os.path.exists(args.script):
            target_script = os.path.abspath(args.script)
            job_name = os.path.splitext(os.path.basename(target_script))[0]
        else:
            job_name = "broken_etl"
            target_script = os.path.abspath("sample_jobs/broken_etl.py")

    result = store.rollback(
        job_name=job_name,
        to_version=target_version,
        target_script_path=target_script,
    )

    print(f"   Target Job:          {job_name}")
    print(f"   Target Version:      {target_version}")
    print(f"   Active Script Path:  {result.get('active_script_path') or target_script}")
    print(f"   Available Snapshots: {result.get('available_versions', [])}")
    print()
    if result["success"]:
        print(f"✅ {result['message']}")
    else:
        print(f"❌ {result['message']}")
    print("=" * 70)


def _heal_aws(args: argparse.Namespace) -> None:
    """Execute the healing pipeline directly against AWS Glue, S3, and CloudWatch."""
    try:
        from .tools.aws import S3ScriptStore, CloudWatchLogFetcher, GlueJobRunner
    except ImportError as e:
        print(f"❌ Failed to import AWS tool suite: {e}")
        print("   Ensure boto3 is installed: pip install boto3")
        sys.exit(1)

    job_name = args.job_name
    if not job_name:
        print("❌ Error: --job-name is required when using --aws mode.")
        print("   Example: python -m gluehealer --aws --job-name my-failing-job")
        sys.exit(1)

    region = args.region or AWS_REGION
    profile = args.profile or AWS_PROFILE

    print("=" * 70)
    print("🩹 GlueHealer AWS Cloud Engine")
    print("=" * 70)
    print(f"   Target Glue Job: {job_name}")
    print(f"   AWS Region:      {region}")
    if profile:
        print(f"   AWS Profile:     {profile}")
    print()

    # Step 1: Connect to Glue and query job definition
    glue_runner = GlueJobRunner(
        job_name=job_name,
        region_name=region,
        profile_name=profile,
    )
    s3_store = S3ScriptStore(
        default_bucket=args.s3_bucket,
        region_name=region,
        profile_name=profile,
    )
    cw_fetcher = CloudWatchLogFetcher(
        region_name=region,
        profile_name=profile,
    )

    print(f"🔍 Fetching job definition for '{job_name}' from AWS Glue...")
    try:
        job_def = glue_runner.get_job_definition()
        s3_script_path = job_def.get("Command", {}).get("ScriptLocation", "")
        if not s3_script_path:
            print(f"❌ Glue job '{job_name}' does not have a Command.ScriptLocation defined.")
            sys.exit(1)
        print(f"   Original S3 script: {s3_script_path}")
    except Exception as e:
        print(f"❌ Could not access AWS Glue job '{job_name}': {e}")
        print("   Check AWS credentials and ensure the job exists.")
        sys.exit(1)

    # Step 2: Ingest error logs from latest failed run or specified run-id
    run_id = args.run_id
    if not run_id:
        print(f"🔍 Searching for latest failed job run of '{job_name}'...")
        failed_run = glue_runner.get_latest_failed_run()
        if failed_run:
            run_id = failed_run.get("Id")
            print(f"   Found failed RunId: {run_id} (State: {failed_run.get('JobRunState')})")
        else:
            print(f"⚠️  No recent failed runs found for job '{job_name}'.")
            trigger = input("   Would you like to trigger a test run now to observe state? [y/N]: ").strip().lower()
            if trigger == "y":
                success, stdout, stderr = glue_runner.run_job(s3_script_path)
                if success:
                    print(f"✅ Glue job '{job_name}' completed successfully — nothing to heal!")
                    return
                print(f"❌ Job run failed. Proceeding with healing...")
            else:
                print("   Exiting. Provide --run-id if you know the specific run.")
                return

    print(f"📋 Ingesting error logs from CloudWatch for run '{run_id}'...")
    error_logs = cw_fetcher.fetch_error_logs(run_id)
    print("--- CloudWatch Error Extracted ---")
    print(error_logs[:600] + ("..." if len(error_logs) > 600 else ""))
    print("----------------------------------\n")

    # Step 3: Build and invoke cloud-connected graph
    graph = build_graph(script_store=s3_store, job_runner=glue_runner)

    initial_state = {
        "job_name": job_name,
        "script_path": s3_script_path,
        "original_script_path": s3_script_path,
        "script_content": "",
        "error_logs": error_logs,
        "historical_patches": [],
        "rca_result": "",
        "corrected_script": "",
        "patch_display": "",
        "human_feedback": "",
        "patched_script_path": "",
        "retry_count": 0,
        "max_retries": args.max_retries,
        "auto_approve": args.auto_approve,
        "demo_mode": args.demo,
        "status": "failed",
        "run_output": "",
    }

    final_state = graph.invoke(initial_state)

    # Step 4: Summary
    print()
    print("=" * 70)
    if final_state["status"] == "healed":
        print("🎉 AWS GLUE JOB HEALED SUCCESSFULLY")
        print(f"   Attempts needed:  {final_state['retry_count']}")
        print(f"   Patches applied:  {len(final_state['historical_patches'])}")
        print(f"   Healed S3 script: {final_state['patched_script_path']}")
        print(f"   Original script:  {final_state['original_script_path']} (unchanged / zero overwrite)")
    elif final_state["status"] == "escalated":
        print("🛑 HEALING FAILED — ESCALATE TO HUMAN ENGINEER")
        print(f"   Attempts made:    {final_state['retry_count']}")
        print(f"   Last error:")
        print(f"   {final_state['error_logs'][:400]}")
    else:
        print(f"⚠️  Pipeline ended with status: {final_state['status']}")
    print("=" * 70)


def _heal_local(args: argparse.Namespace) -> None:
    """Execute the healing pipeline locally on the filesystem."""
    script_path = os.path.abspath(args.script)
    job_name = args.job_name or os.path.splitext(os.path.basename(script_path))[0]

    if not os.path.exists(script_path):
        print(f"❌ Script not found: {script_path}")
        sys.exit(1)

    if args.demo:
        print("🎭 Running GlueHealer in OFFLINE DEMO mode (Zero API keys needed)")

    # Step 1: Run script locally to check for failure
    print(f"🔍 Running job '{job_name}' to check for failures...")
    print(f"   Script: {script_path}\n")

    runner = LocalJobRunner()
    success, stdout, stderr = runner.run_job(script_path)

    if success:
        print(f"✅ Job '{job_name}' ran successfully — nothing to heal!")
        if stdout.strip():
            print(f"Output:\n{stdout}")
        return

    print(f"❌ Job '{job_name}' failed. Starting healing pipeline...\n")
    print(f"Error:\n{stderr}")

    # Step 2: Build and invoke local graph
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
        "demo_mode": args.demo,
        "status": "failed",
        "run_output": "",
    }

    final_state = graph.invoke(initial_state)

    # Step 3: Summary
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


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="gluehealer",
        description="GlueHealer — self-healing agent for failed AWS Glue and ETL jobs",
    )
    parser.add_argument(
        "commands",
        nargs="*",
        default=[],
        help="Command ('demo', 'rollback') or path to the script to heal (default: sample_jobs/broken_etl.py)",
    )
    parser.add_argument(
        "--aws",
        action="store_true",
        help="Run in AWS Cloud mode (connects to AWS Glue, CloudWatch, and S3)",
    )
    parser.add_argument(
        "--job-name",
        help="AWS Glue job name (or local job name)",
    )
    parser.add_argument(
        "--run-id",
        help="Specific AWS Glue JobRunId to triage (optional, defaults to latest failed run)",
    )
    parser.add_argument(
        "--s3-bucket",
        help="Override target S3 bucket for versioned scripts",
    )
    parser.add_argument(
        "--region",
        default=AWS_REGION,
        help=f"AWS region (default: {AWS_REGION})",
    )
    parser.add_argument(
        "--profile",
        default=AWS_PROFILE,
        help="AWS CLI credential profile",
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Run in offline showcase demo mode (requires zero API keys)",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=MAX_RETRIES,
        help=f"Maximum healing attempts (default: {MAX_RETRIES})",
    )
    parser.add_argument(
        "--auto-approve",
        action="store_true",
        help="Automatically approve patches without human confirmation prompt",
    )
    parser.add_argument(
        "--to-version",
        default="original",
        help="Target version to roll back to: 'original' or 'v1', 'v2', etc. (default: 'original')",
    )
    parser.add_argument(
        "--to-s3-path",
        help="Target S3 script URI to point AWS Glue job to during rollback",
    )
    parser.add_argument(
        "--restore-worker-type",
        help="WorkerType to restore during rollback (e.g. G.1X)",
    )
    parser.add_argument(
        "--restore-num-workers",
        type=int,
        help="NumberOfWorkers to restore during rollback (e.g. 2)",
    )

    args = parser.parse_args()

    # Determine command or script target
    first_cmd = args.commands[0] if args.commands else None

    if first_cmd == "rollback":
        args.script = args.commands[1] if len(args.commands) > 1 else None
        _handle_rollback(args)
        return

    if first_cmd == "demo":
        args.script = "sample_jobs/broken_etl.py"
        args.demo = True
    elif first_cmd:
        args.script = first_cmd
    else:
        args.script = "sample_jobs/broken_etl.py"

    if args.aws:
        _heal_aws(args)
    else:
        _heal_local(args)


if __name__ == "__main__":
    main()
