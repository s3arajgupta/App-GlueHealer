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

    def run_job(self, script_path: str, config: dict | None = None) -> Tuple[bool, str, str]:
        if config and config.get("WorkerType") in ("G.2X", "G.4X"):
            # When auto-tuning memory allocation in simulation/local runs
            print(f"   ⚙️  Subprocess running with auto-tuned environment ({config.get('WorkerType')}, {config.get('NumberOfWorkers')} Workers)")
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
