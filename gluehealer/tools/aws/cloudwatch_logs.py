"""
AWS CloudWatch Logs fetcher for GlueHealer.

Extracts fatal exceptions and stack traces from AWS Glue log groups:
  - /aws-glue/jobs/error
  - /aws-glue/python-jobs/output
  - /aws-glue/jobs/output

Filters out Spark heartbeat and diagnostic noise to present concise error context
to the RCA Analyzer agent.
"""
from __future__ import annotations

import re
import boto3
from botocore.exceptions import ClientError

from ...config import AWS_REGION, AWS_PROFILE


class CloudWatchLogFetcher:
    """Fetches and isolates error stack traces for failed AWS Glue job runs."""

    DEFAULT_LOG_GROUPS = [
        "/aws-glue/jobs/error",
        "/aws-glue/python-jobs/output",
        "/aws-glue/jobs/output",
    ]

    def __init__(
        self,
        region_name: str | None = None,
        profile_name: str | None = None,
        logs_client=None,
    ):
        if logs_client:
            self.logs = logs_client
        else:
            session = boto3.Session(
                profile_name=profile_name or AWS_PROFILE,
                region_name=region_name or AWS_REGION,
            )
            self.logs = session.client("logs")

    def fetch_error_logs(
        self,
        job_run_id: str,
        log_group: str | None = None,
        max_lines: int = 100,
    ) -> str:
        """
        Fetch error logs for a specific job_run_id across default Glue log groups.
        Returns the formatted error and isolated stack trace.
        """
        log_groups_to_check = [log_group] if log_group else self.DEFAULT_LOG_GROUPS

        for group in log_groups_to_check:
            try:
                # Look for log stream matching the run_id
                streams = self.logs.describe_log_streams(
                    logGroupName=group,
                    logStreamNamePrefix=job_run_id,
                    orderBy="LastEventTime",
                    descending=True,
                    limit=5,
                )

                stream_list = streams.get("logStreams", [])
                if not stream_list:
                    # Fallback: search for any stream containing run_id
                    all_recent = self.logs.describe_log_streams(
                        logGroupName=group,
                        orderBy="LastEventTime",
                        descending=True,
                        limit=10,
                    )
                    stream_list = [
                        s for s in all_recent.get("logStreams", [])
                        if job_run_id in s.get("logStreamName", "")
                    ]

                if not stream_list:
                    continue

                target_stream = stream_list[0]["logStreamName"]

                events = self.logs.get_log_events(
                    logGroupName=group,
                    logStreamName=target_stream,
                    limit=max_lines,
                    startFromHead=False,
                )

                messages = [e["message"] for e in events.get("events", [])]
                if messages:
                    raw_text = "\n".join(messages)
                    return self.isolate_stack_trace(raw_text)

            except ClientError as e:
                # Group might not exist in this account / region, check next
                code = e.response.get("Error", {}).get("Code", "")
                if code in ("ResourceNotFoundException", "AccessDeniedException"):
                    continue
                continue

        return f"(No CloudWatch error logs found in {log_groups_to_check} for run_id '{job_run_id}')"

    @staticmethod
    def isolate_stack_trace(raw_logs: str) -> str:
        """
        Extract the fatal exception and python stack trace from noisy Glue/Spark logs.
        """
        lines = raw_logs.splitlines()

        # Check if traceback is present
        traceback_indices = [
            i for i, line in enumerate(lines) if "Traceback (most recent call last):" in line
        ]

        if traceback_indices:
            # Grab from the last traceback onwards
            start_idx = traceback_indices[-1]
            extracted = lines[start_idx : start_idx + 60]
            return "\n".join(extracted)

        # Fallback: Look for ERROR or Exception lines
        error_lines = [
            line for line in lines
            if any(term in line for term in ("ERROR", "Exception", "Error:", "Failed", "KeyError", "ValueError"))
        ]

        if error_lines:
            return "\n".join(error_lines[-30:])

        return raw_logs[-2000:] if len(raw_logs) > 2000 else raw_logs
