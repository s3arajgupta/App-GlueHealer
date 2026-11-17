"""
Abstract interfaces for GlueHealer tools.

Local implementations live in tools/local/.
AWS implementations (Phase 2) will live in tools/aws/.
"""
from abc import ABC, abstractmethod
from typing import Tuple


class ScriptStore(ABC):
    """Reads and writes ETL job scripts (S3 in production, filesystem locally)."""

    @abstractmethod
    def read_script(self, path: str) -> str:
        """Return the full text of the script at *path*."""
        ...

    @abstractmethod
    def write_script(self, path: str, content: str) -> str:
        """Overwrite the script at *path*. Return the path written to."""
        ...

    @abstractmethod
    def create_version(self, job_name: str, content: str, version: int, original_path: str | None = None) -> str:
        """Save a versioned snapshot and return the new path."""
        ...


class JobRunner(ABC):
    """Runs an ETL job and returns its result (Glue in production, subprocess locally)."""

    @abstractmethod
    def run_job(self, script_path: str, config: dict | None = None) -> Tuple[bool, str, str]:
        """
        Execute the job with optional resource configuration.

        Returns:
            (success, stdout, stderr)
        """
        ...
