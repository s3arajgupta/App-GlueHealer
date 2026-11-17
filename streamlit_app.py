"""
Streamlit Community Cloud Entrypoint for GlueHealer.

Streamlit Community Cloud detects this file automatically at the root of the repository.
It sets up the environment and executes the GlueHealer UI control center.
"""
import os
import sys
import runpy

# Ensure repository root is on sys.path
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

# Run the GlueHealer UI application
app_path = os.path.join(ROOT_DIR, "gluehealer", "ui", "app.py")
runpy.run_path(app_path, run_name="__main__")
