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

    def run_job(self, script_path: str) -> Tuple[bool, str, str]:
        """
        Execute the Glue job with the given script path.
        Points the job definition to script_path (if on S3), starts a run,
        and polls until completion.
        """
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
