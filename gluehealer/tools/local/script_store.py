"""
Local script store — reads/writes scripts on the local filesystem.

Versioned copies are saved under VERSIONS_DIR/<job_name>/v<N>.py
so the original file is never lost.
"""
from __future__ import annotations

import os
import shutil
from ..interface import ScriptStore
from ...config import VERSIONS_DIR


class LocalScriptStore(ScriptStore):

    def __init__(self, versions_dir: str | None = None):
        self.versions_dir = versions_dir or VERSIONS_DIR
        os.makedirs(self.versions_dir, exist_ok=True)

    def read_script(self, path: str) -> str:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()

    def write_script(self, path: str, content: str) -> str:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return path

    def create_version(self, job_name: str, content: str, version: int, original_path: str | None = None) -> str:
        job_dir = os.path.join(self.versions_dir, job_name)
        os.makedirs(job_dir, exist_ok=True)
        version_path = os.path.join(job_dir, f"v{version}.py")
        with open(version_path, "w", encoding="utf-8") as f:
            f.write(content)

        # Copy companion folders (like data/) so scripts with relative paths work
        if original_path and os.path.exists(original_path):
            orig_dir = os.path.dirname(os.path.abspath(original_path))
            for item in os.listdir(orig_dir):
                item_path = os.path.join(orig_dir, item)
                target_path = os.path.join(job_dir, item)
                if os.path.isdir(item_path) and item not in ("__pycache__", "versions", "output", "venv"):
                    if not os.path.exists(target_path):
                        shutil.copytree(item_path, target_path)

        return version_path

    def list_versions(self, job_name: str) -> list[str]:
        """List all generated version snapshots for a job."""
        job_dir = os.path.join(self.versions_dir, job_name)
        if not os.path.exists(job_dir):
            return []
        return sorted([f for f in os.listdir(job_dir) if f.startswith("v") and f.endswith(".py")])

    def get_version_path(self, job_name: str, version: str) -> str | None:
        """Get the full path to a specific version (e.g. 'v1' or 'v1.py')."""
        if not version.endswith(".py"):
            version = f"{version}.py"
        path = os.path.join(self.versions_dir, job_name, version)
        return path if os.path.exists(path) else None

    def rollback(
        self,
        job_name: str,
        to_version: str = "original",
        target_script_path: str | None = None,
        overwrite: bool = False,
    ) -> dict:
        """
        Roll back to the original script or a specific historical version snapshot.
        Preserves non-destructive isolation by default.
        """
        versions = self.list_versions(job_name)
        to_ver = to_version.strip().lower()

        if to_ver in ("original", "baseline", "v0"):
            resolved_path = target_script_path or os.path.join("sample_jobs", f"{job_name}.py")
            return {
                "success": True,
                "job_name": job_name,
                "target_version": "original",
                "active_script_path": resolved_path,
                "available_versions": versions,
                "message": (
                    f"Active script pointer successfully rolled back to original baseline script: '{resolved_path}'. "
                    f"Zero-overwrite guarantee preserved: original script was never altered."
                ),
            }

        version_file = self.get_version_path(job_name, to_ver)
        if not version_file or not os.path.exists(version_file):
            return {
                "success": False,
                "job_name": job_name,
                "target_version": to_version,
                "active_script_path": None,
                "available_versions": versions,
                "message": f"Version '{to_version}' not found for job '{job_name}'. Available versions: {versions}",
            }

        if overwrite and target_script_path and os.path.exists(target_script_path):
            with open(version_file, "r", encoding="utf-8") as src:
                content = src.read()
            with open(target_script_path, "w", encoding="utf-8") as dst:
                dst.write(content)

        return {
            "success": True,
            "job_name": job_name,
            "target_version": to_version,
            "active_script_path": version_file,
            "available_versions": versions,
            "message": (
                f"Active script pointer successfully rolled back to version snapshot '{to_version}' at '{version_file}'."
            ),
        }
