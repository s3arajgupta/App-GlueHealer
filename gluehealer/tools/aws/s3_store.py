"""
AWS S3 script store implementation for GlueHealer.

Reads original scripts from S3 and saves versioned snapshots
under s3://<bucket>/gluehealer-versions/<job_name>/v<N>.py so original scripts
are never modified in place.
"""
from __future__ import annotations

import os
from urllib.parse import urlparse
import boto3
from botocore.exceptions import ClientError

from ..interface import ScriptStore
from ...config import AWS_REGION, AWS_PROFILE, S3_VERSIONS_PREFIX


class S3ScriptStore(ScriptStore):
    """Stores and retrieves ETL scripts from Amazon S3 with non-destructive versioning."""

    def __init__(
        self,
        default_bucket: str | None = None,
        region_name: str | None = None,
        profile_name: str | None = None,
        versions_prefix: str | None = None,
        s3_client=None,
    ):
        self.default_bucket = default_bucket
        self.versions_prefix = versions_prefix or S3_VERSIONS_PREFIX

        if s3_client:
            self.s3 = s3_client
        else:
            session = boto3.Session(
                profile_name=profile_name or AWS_PROFILE,
                region_name=region_name or AWS_REGION,
            )
            self.s3 = session.client("s3")

    @staticmethod
    def parse_s3_uri(uri: str) -> tuple[str, str]:
        """Parse an s3://bucket/key URI into (bucket, key)."""
        parsed = urlparse(uri)
        if parsed.scheme != "s3" or not parsed.netloc:
            raise ValueError(f"Invalid S3 URI: '{uri}'. Expected format: s3://bucket/key")
        return parsed.netloc, parsed.path.lstrip("/")

    def read_script(self, path: str) -> str:
        """Download and return the text content of an S3 script."""
        if not path.startswith("s3://"):
            # Fallback to local filesystem if not an S3 URI (useful in hybrid workflows)
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    return f.read()
            raise ValueError(f"Path must be an s3:// URI or existing local path: {path}")

        bucket, key = self.parse_s3_uri(path)
        try:
            response = self.s3.get_object(Bucket=bucket, Key=key)
            return response["Body"].read().decode("utf-8")
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            raise RuntimeError(
                f"Failed to read S3 script at s3://{bucket}/{key} ({error_code}): {e}"
            ) from e

    def write_script(self, path: str, content: str) -> str:
        """Write text content to an S3 path."""
        bucket, key = self.parse_s3_uri(path)
        try:
            self.s3.put_object(
                Bucket=bucket,
                Key=key,
                Body=content.encode("utf-8"),
                ContentType="text/x-python",
            )
            return path
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            raise RuntimeError(
                f"Failed to write S3 script to s3://{bucket}/{key} ({error_code}): {e}"
            ) from e

    def create_version(
        self,
        job_name: str,
        content: str,
        version: int,
        original_path: str | None = None,
    ) -> str:
        """
        Save a non-destructive versioned copy to S3:
        s3://<bucket>/gluehealer-versions/<job_name>/v<version>.py
        """
        bucket = None
        if original_path and original_path.startswith("s3://"):
            bucket, _ = self.parse_s3_uri(original_path)
        elif self.default_bucket:
            bucket = self.default_bucket

        if not bucket:
            raise ValueError(
                "Cannot determine target S3 bucket for versioned script. "
                "Provide an original s3:// path or set default_bucket."
            )

        key = f"{self.versions_prefix}/{job_name}/v{version}.py"
        target_uri = f"s3://{bucket}/{key}"

        try:
            self.s3.put_object(
                Bucket=bucket,
                Key=key,
                Body=content.encode("utf-8"),
                ContentType="text/x-python",
                Metadata={
                    "gluehealer-version": str(version),
                    "gluehealer-job": job_name,
                    "gluehealer-original": str(original_path or "unknown"),
                },
            )
            return target_uri
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            raise RuntimeError(
                f"Failed to upload versioned script to {target_uri} ({error_code}): {e}"
            ) from e
