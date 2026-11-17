"""
Unit tests for AWS Cloud tool adapters (S3ScriptStore & CloudWatchLogFetcher).
"""
import pytest
from gluehealer.tools.aws.s3_store import S3ScriptStore
from gluehealer.tools.aws.cloudwatch_logs import CloudWatchLogFetcher


def test_parse_s3_uri_valid():
    bucket, key = S3ScriptStore.parse_s3_uri("s3://my-datalake-bucket/scripts/etl_job.py")
    assert bucket == "my-datalake-bucket"
    assert key == "scripts/etl_job.py"


def test_parse_s3_uri_nested():
    bucket, key = S3ScriptStore.parse_s3_uri("s3://company/prod/silver/transform.py")
    assert bucket == "company"
    assert key == "prod/silver/transform.py"


def test_parse_s3_uri_invalid():
    with pytest.raises(ValueError):
        S3ScriptStore.parse_s3_uri("https://s3.amazonaws.com/bucket/key")

    with pytest.raises(ValueError):
        S3ScriptStore.parse_s3_uri("/local/path/to/script.py")


def test_cloudwatch_isolate_stack_trace_from_spark_noise():
    noisy_spark_logs = """
2026-11-17 04:00:01 INFO BlockManager: Got updated block statuses for block broadcast_1_piece0
2026-11-17 04:00:02 INFO HeartbeatReceiver: Received heartbeat from executor-1
2026-11-17 04:00:03 ERROR Executor: Exception in task 0.0 in stage 1.0 (TID 1)
Traceback (most recent call last):
  File "job.py", line 42, in <module>
    main()
  File "job.py", line 25, in transform
    "total": record["quantity"] * record["unit_price"]
KeyError: 'unit_price'
2026-11-17 04:00:04 INFO TaskSetManager: Task 0.0 in stage 1.0 failed
2026-11-17 04:00:05 INFO DAGScheduler: Job 0 failed
"""
    cleaned = CloudWatchLogFetcher.isolate_stack_trace(noisy_spark_logs)
    assert "Traceback (most recent call last):" in cleaned
    assert "KeyError: 'unit_price'" in cleaned
    assert "BlockManager: Got updated block" not in cleaned
