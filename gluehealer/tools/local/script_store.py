"""
Local script store — reads/writes scripts on the local filesystem.

Versioned copies are saved under VERSIONS_DIR/<job_name>/v<N>.py
so the original file is never lost.
"""
import os
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
                        import shutil
                        shutil.copytree(item_path, target_path)

        return version_path
