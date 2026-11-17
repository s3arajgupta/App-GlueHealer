"""
Local job runner — executes Python scripts as subprocesses.

This simulates AWS Glue job execution for local development.
"""
import subprocess
import sys
from typing import Tuple
from ..interface import JobRunner


class LocalJobRunner(JobRunner):

    def __init__(self, timeout: int = 60):
        self.timeout = timeout

    def run_job(self, script_path: str) -> Tuple[bool, str, str]:
        try:
            result = subprocess.run(
                [sys.executable, script_path],
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )
            success = result.returncode == 0
            return success, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            return False, "", f"Job timed out after {self.timeout} seconds"
        except Exception as e:
            return False, "", f"Job runner error: {e}"
