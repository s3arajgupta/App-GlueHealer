"""
Unit tests for the cyclic state machine and routing logic.
"""
import os
import shutil
import tempfile
import pytest

from gluehealer.graph import build_graph
from gluehealer.tools.local import LocalScriptStore, LocalJobRunner


@pytest.fixture
def temp_workspace():
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


def test_state_machine_healing_demo_mode(temp_workspace):
    """Test full cycle in demo mode: detection -> RCA -> patch -> apply -> retry -> healed."""
    script_content = """# Test ETL
def main():
    record = {"price": 10.0, "quantity": 2}
    total = record["quantity"] * record["unit_price"]
    print("Done")

if __name__ == "__main__":
    main()
"""
    script_path = os.path.join(temp_workspace, "test_job.py")
    with open(script_path, "w", encoding="utf-8") as f:
        f.write(script_content)

    store = LocalScriptStore(versions_dir=os.path.join(temp_workspace, "versions"))
    runner = LocalJobRunner()
    graph = build_graph(script_store=store, job_runner=runner)

    initial_state = {
        "job_name": "test_job",
        "script_path": script_path,
        "original_script_path": script_path,
        "script_content": "",
        "error_logs": "KeyError: 'unit_price'",
        "historical_patches": [],
        "rca_result": "",
        "corrected_script": "",
        "patch_display": "",
        "human_feedback": "",
        "patched_script_path": "",
        "retry_count": 0,
        "max_retries": 3,
        "auto_approve": True,
        "demo_mode": True,
        "status": "failed",
        "run_output": "",
    }

    final_state = graph.invoke(initial_state)

    assert final_state["status"] == "healed"
    assert final_state["retry_count"] == 1
    assert os.path.exists(final_state["patched_script_path"])
    # Verify original script is untouched (zero-overwrite guarantee)
    with open(script_path, "r", encoding="utf-8") as f:
        assert 'record["unit_price"]' in f.read()


def test_escalation_on_persistent_failure(temp_workspace):
    """Test that jobs escalate after exceeding max_retries."""
    # Script that will always fail
    script_content = "raise RuntimeError('Permanent database connection failure')"
    script_path = os.path.join(temp_workspace, "failing_job.py")
    with open(script_path, "w", encoding="utf-8") as f:
        f.write(script_content)

    store = LocalScriptStore(versions_dir=os.path.join(temp_workspace, "versions"))
    runner = LocalJobRunner()
    graph = build_graph(script_store=store, job_runner=runner)

    initial_state = {
        "job_name": "failing_job",
        "script_path": script_path,
        "original_script_path": script_path,
        "script_content": "",
        "error_logs": "RuntimeError: Permanent database connection failure",
        "historical_patches": [],
        "rca_result": "",
        "corrected_script": "",
        "patch_display": "",
        "human_feedback": "",
        "patched_script_path": "",
        "retry_count": 0,
        "max_retries": 2,  # Cap at 2
        "auto_approve": True,
        "demo_mode": True,
        "status": "failed",
        "run_output": "",
    }

    final_state = graph.invoke(initial_state)

    assert final_state["status"] == "escalated"
    assert final_state["retry_count"] == 2
