"""
CLI entrypoint to launch the GlueHealer Streamlit UI.

Usage:
    python -m gluehealer.ui
"""
import os
import sys
from streamlit.web import cli as stcli


def main():
    app_path = os.path.join(os.path.dirname(__file__), "app.py")
    sys.argv = ["streamlit", "run", app_path]
    sys.exit(stcli.main())


if __name__ == "__main__":
    main()
