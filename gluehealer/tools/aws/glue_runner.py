"""
AWS Glue job runner implementation for GlueHealer.

Starts Glue job runs, points the job definition to versioned S3 scripts,
polls job execution status with exponential backoff, and retrieves CloudWatch error
logs upon failure.
"""
from __future__ import annotations

import time
from typing import Tuple
import boto3
from botocore.exceptions import ClientError

from ..interface import JobRunner
from .cloudwatch_logs import CloudWatchLogFetcher
from ...config import AWS_REGION, AWS_PROFILE


class GlueJobRunner(JobRunner):
    """Executes and monitors AWS Glue jobs in the cloud."""

    TERMINAL_STATES = {"SUCCEEDED", "FAILED", "TIMEOUT", "STOPPED", "ERROR"}

    def __init__(
        self,
        job_name: str,
        region_name: str | None = None,
        profile_name: str | None = None,
        poll_interval: int = 5,
        timeout: int = 600,
        glue_client=None,
        log_fetcher: CloudWatchLogFetcher | None = None,
    ):
        self.job_name = job_name
        self.poll_interval = poll_interval
        self.timeout = timeout

        if glue_client:
            self.glue = glue_client
        else:
            session = boto3.Session(
                profile_name=profile_name or AWS_PROFILE,
                region_name=region_name or AWS_REGION,
            )
            self.glue = session.client("glue")

        self.log_fetcher = log_fetcher or CloudWatchLogFetcher(
            region_name=region_name,
            profile_name=profile_name,
        )

    def get_job_definition(self) -> dict:
        """Fetch the current AWS Glue job configuration."""
        try:
            resp = self.glue.get_job(JobName=self.job_name)
            return resp.get("Job", {})
        except ClientError as e:
            code = e.response.get("Error", {}).get("Code", "Unknown")
            raise RuntimeError(f"Could not retrieve Glue job '{self.job_name}' ({code}): {e}") from e

    def get_latest_failed_run(self) -> dict | None:
        """Find the most recent failed, timed out, or error job run."""
        try:
            resp = self.glue.get_job_runs(JobName=self.job_name, MaxResults=10)
            runs = resp.get("JobRuns", [])
            for run in runs:
                if run.get("JobRunState") in ("FAILED", "TIMEOUT", "ERROR", "STOPPED"):
                    return run
            return None
        except ClientError as e:
            code = e.response.get("Error", {}).get("Code", "Unknown")
            raise RuntimeError(f"Failed to query job runs for '{self.job_name}' ({code}): {e}") from e

    def update_job_script(self, new_script_s3_path: str) -> None:
        """Update the Glue job's Command.ScriptLocation to point to the patched S3 script."""
        current_job = self.get_job_definition()
        command = current_job.get("Command", {})
        command["ScriptLocation"] = new_script_s3_path

        job_update = {
            "Role": current_job.get("Role"),
            "Command": command,
            "DefaultArguments": current_job.get("DefaultArguments", {}),
            "GlueVersion": current_job.get("GlueVersion", "4.0"),
        }

        # Preserve worker type & count if defined
        if "WorkerType" in current_job:
            job_update["WorkerType"] = current_job["WorkerType"]
        if "NumberOfWorkers" in current_job:
            job_update["NumberOfWorkers"] = current_job["NumberOfWorkers"]

        try:
            self.glue.update_job(JobName=self.job_name, JobUpdate=job_update)
            print(f"   ☁️ Updated Glue job '{self.job_name}' ScriptLocation → {new_script_s3_path}")
        except ClientError as e:
            code = e.response.get("Error", {}).get("Code", "Unknown")
            raise RuntimeError(f"Failed to update Glue job script ({code}): {e}") from e

    def update_job_resources(
        self,
        worker_type: str | None = None,
        num_workers: int | None = None,
        timeout: int | None = None,
    ) -> None:
        """Update Glue worker type, worker count, or timeout in AWS Glue."""
        current_job = self.get_job_definition()
        job_update = {
            "Role": current_job.get("Role"),
            "Command": current_job.get("Command", {}),
            "DefaultArguments": current_job.get("DefaultArguments", {}),
            "GlueVersion": current_job.get("GlueVersion", "4.0"),
        }
        if worker_type:
            job_update["WorkerType"] = worker_type
        elif "WorkerType" in current_job:
            job_update["WorkerType"] = current_job["WorkerType"]

        if num_workers:
            job_update["NumberOfWorkers"] = num_workers
        elif "NumberOfWorkers" in current_job:
            job_update["NumberOfWorkers"] = current_job["NumberOfWorkers"]

        if timeout:
            job_update["Timeout"] = timeout
        elif "Timeout" in current_job:
            job_update["Timeout"] = current_job["Timeout"]

        try:
            self.glue.update_job(JobName=self.job_name, JobUpdate=job_update)
            print(f"   ☁️ Auto-tuned Glue job '{self.job_name}' resources: WorkerType={job_update.get('WorkerType')}, Workers={job_update.get('NumberOfWorkers')}")
        except ClientError as e:
            code = e.response.get("Error", {}).get("Code", "Unknown")
            raise RuntimeError(f"Failed to update Glue job resources ({code}): {e}") from e

    def rollback(
        self,
        to_script_s3_path: str,
        restore_worker_type: str | None = None,
        restore_num_workers: int | None = None,
    ) -> bool:
        """Roll back Glue job configuration to a previous script version or baseline config."""
        current_job = self.get_job_definition()
        command = current_job.get("Command", {})
        command["ScriptLocation"] = to_script_s3_path

        job_update = {
            "Role": current_job.get("Role"),
            "Command": command,
            "DefaultArguments": current_job.get("DefaultArguments", {}),
            "GlueVersion": current_job.get("GlueVersion", "4.0"),
        }
        if restore_worker_type:
            job_update["WorkerType"] = restore_worker_type
        elif "WorkerType" in current_job:
            job_update["WorkerType"] = current_job["WorkerType"]

        if restore_num_workers:
            job_update["NumberOfWorkers"] = restore_num_workers
        elif "NumberOfWorkers" in current_job:
            job_update["NumberOfWorkers"] = current_job["NumberOfWorkers"]

        try:
            self.glue.update_job(JobName=self.job_name, JobUpdate=job_update)
            return True
        except ClientError as e:
            code = e.response.get("Error", {}).get("Code", "Unknown")
            raise RuntimeError(f"Rollback failed for job '{self.job_name}' ({code}): {e}") from e

    def run_job(self, script_path: str, config: dict | None = None) -> Tuple[bool, str, str]:
        """
        Execute the Glue job with the given script path and optional resource configuration.
        Points the job definition to script_path (if on S3), applies resource scaling (if provided),
        starts a run, and polls until completion.
        """
        # If resource config is passed, auto-tune worker allocation
        if config:
            self.update_job_resources(
                worker_type=config.get("WorkerType"),
                num_workers=config.get("NumberOfWorkers"),
                timeout=config.get("Timeout"),
            )

        # If script_path is an S3 URI, update the job configuration
        if script_path.startswith("s3://"):
            self.update_job_script(script_path)

        print(f"   ☁️ Triggering AWS Glue start_job_run for '{self.job_name}'...")
        try:
            resp = self.glue.start_job_run(JobName=self.job_name)
            run_id = resp["JobRunId"]
            print(f"   🚀 Job run started with RunId: {run_id}")
        except ClientError as e:
            code = e.response.get("Error", {}).get("Code", "Unknown")
            return False, "", f"Failed to start AWS Glue job run ({code}): {e}"

        # Polling loop
        start_time = time.time()
        current_interval = self.poll_interval

        while True:
            if time.time() - start_time > self.timeout:
                return False, "", f"Job run {run_id} timed out after {self.timeout} seconds"

            time.sleep(current_interval)
            # Gentle exponential backoff up to 15 seconds
            current_interval = min(current_interval * 1.2, 15)

            try:
                run_status = self.glue.get_job_run(JobName=self.job_name, RunId=run_id)["JobRun"]
                state = run_status.get("JobRunState")
                elapsed = int(time.time() - start_time)
                print(f"   ⏳ Run {run_id} status: {state} ({elapsed}s elapsed)...", flush=True)

                if state == "SUCCEEDED":
                    stdout = f"AWS Glue Job '{self.job_name}' run '{run_id}' completed SUCCEEDED in {elapsed}s."
                    return True, stdout, ""

                if state in ("FAILED", "TIMEOUT", "STOPPED", "ERROR"):
                    error_msg = run_status.get("ErrorMessage", f"Job ended in state {state}")
                    # Ingest CloudWatch error logs
                    cw_logs = self.log_fetcher.fetch_error_logs(run_id)
                    combined_err = f"{error_msg}\n\n[CloudWatch Error Logs]:\n{cw_logs}"
                    return False, "", combined_err

            except ClientError as e:
                code = e.response.get("Error", {}).get("Code", "Unknown")
                return False, "", f"Error polling job run {run_id} ({code}): {e}"
