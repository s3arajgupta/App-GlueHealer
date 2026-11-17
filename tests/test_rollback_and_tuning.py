"""
Unit tests for Infrastructure / OOM Auto-Tuning and One-Click Rollback.
"""
import os
import shutil
import tempfile
from unittest.mock import MagicMock
import pytest

from gluehealer.agents.rca_analyzer import rca_analyzer
from gluehealer.agents.patch_generator import patch_generator
from gluehealer.tools.local import LocalScriptStore
from gluehealer.tools.aws import GlueJobRunner


@pytest.fixture
def temp_workspace():
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


def test_rca_classifies_oom_as_infrastructure():
    """Verify that YARN / OOM exit code 137 errors are classified as infrastructure bottlenecks."""
    state = {
        "error_logs": (
            "2026-11-18T05:10:28.110Z [ERROR] Container killed by YARN for exceeding memory limits: "
            "16.0 GB of 16.0 GB physical memory used.\n"
            "ExecutorLostFailure (executor 1 exited with exit code 137)"
        ),
        "demo_mode": True,
        "script_content": "df.join(other_df)",
    }
    result = rca_analyzer(state)
    assert result["failure_category"] == "infrastructure"
    assert "G.1X" in result["rca_result"]
    assert "G.2X" in result["rca_result"]


def test_patch_generator_tunes_glue_resources():
    """Verify that infrastructure bottlenecks trigger resource auto-tuning rather than code mutation."""
    state = {
        "failure_category": "infrastructure",
        "error_logs": "Container killed by YARN for exceeding memory limits (Exit code 137)",
        "script_content": "df = spark.read.parquet(...)",
        "current_job_config": {
            "WorkerType": "G.1X",
            "NumberOfWorkers": 2,
            "Timeout": 60,
        },
    }
    result = patch_generator(state)
    assert result["status"] == "patch_ready"
    assert result["proposed_job_config"]["WorkerType"] == "G.2X"
    assert result["proposed_job_config"]["NumberOfWorkers"] == 4
    # Script content remains unmodified because it is an infra bottleneck
    assert result["corrected_script"] == "df = spark.read.parquet(...)"
    assert "+ WorkerType: G.2X" in result["patch_display"]


def test_local_store_rollback_to_original(temp_workspace):
    """Verify rollback to original baseline preserves zero-overwrite guarantee."""
    job_name = "test_etl"
    versions_dir = os.path.join(temp_workspace, "versions")
    store = LocalScriptStore(versions_dir=versions_dir)

    # Create dummy versions v1, v2
    store.create_version(job_name, "# v1 code", 1)
    store.create_version(job_name, "# v2 code", 2)

    assert store.list_versions(job_name) == ["v1.py", "v2.py"]

    # Roll back to original baseline
    res = store.rollback(job_name, to_version="original")
    assert res["success"] is True
    assert res["target_version"] == "original"
    assert "zero lines were overwritten" in res["message"] or "never altered" in res["message"]


def test_local_store_rollback_to_version(temp_workspace):
    """Verify rollback to a specific snapshot version."""
    job_name = "test_etl"
    versions_dir = os.path.join(temp_workspace, "versions")
    store = LocalScriptStore(versions_dir=versions_dir)

    v1_path = store.create_version(job_name, "# v1 code", 1)
    store.create_version(job_name, "# v2 code", 2)

    res = store.rollback(job_name, to_version="v1")
    assert res["success"] is True
    assert res["target_version"] == "v1"
    assert res["active_script_path"] == v1_path

    # Non-existent version
    res_bad = store.rollback(job_name, to_version="v99")
    assert res_bad["success"] is False
    assert "not found" in res_bad["message"]


def test_aws_glue_runner_rollback_updates_job():
    """Verify GlueJobRunner.rollback updates Glue job with target S3 script and restored resources."""
    mock_glue = MagicMock()
    mock_glue.get_job.return_value = {
        "Job": {
            "Role": "arn:aws:iam::123456789012:role/GlueRole",
            "Command": {"Name": "glueetl", "ScriptLocation": "s3://bucket/gluehealer-versions/job/v2.py"},
            "WorkerType": "G.2X",
            "NumberOfWorkers": 4,
            "DefaultArguments": {},
            "GlueVersion": "4.0",
        }
    }

    runner = GlueJobRunner(job_name="mock-glue-job", glue_client=mock_glue)
    success = runner.rollback(
        to_script_s3_path="s3://bucket/scripts/original_job.py",
        restore_worker_type="G.1X",
        restore_num_workers=2,
    )

    assert success is True
    mock_glue.update_job.assert_called_once()
    call_kwargs = mock_glue.update_job.call_args[1]
    assert call_kwargs["JobName"] == "mock-glue-job"
    update = call_kwargs["JobUpdate"]
    assert update["Command"]["ScriptLocation"] == "s3://bucket/scripts/original_job.py"
    assert update["WorkerType"] == "G.1X"
    assert update["NumberOfWorkers"] == 2
