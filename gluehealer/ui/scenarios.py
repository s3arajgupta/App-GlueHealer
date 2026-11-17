"""
GlueHealer Showcase Scenarios.

Realistic mock production scenarios simulating AWS Glue ETL failures, CloudWatch
error logs, root-cause analyses, code diffs, and cyclic human feedback loops.
Used for zero-friction demonstrations in interviews and portfolio reviews.
"""
from __future__ import annotations

SCENARIOS = {
    "sales_schema_drift": {
        "id": "sales_schema_drift",
        "title": "🛒 Orders Bronze-to-Silver (Schema Drift KeyError)",
        "job_name": "orders-bronze-to-silver",
        "dpu": 2,
        "glue_type": "Spark ETL",
        "cloudwatch_log_group": "/aws-glue/jobs/error",
        "job_run_id": "jr_8f39b1a03e91c4b2",
        "s3_original_path": "s3://corporate-datalake-prod/scripts/orders_bronze_silver.py",
        "error_type": "KeyError: 'unit_price'",
        "summary": "Daily sales transaction batch failed due to upstream ERP updating column header from 'unit_price' to 'price'.",
        "raw_error_logs": """2026-11-17T03:15:21.012Z [INFO] Initializing AWS Glue Spark Session (JobRunId: jr_8f39b1a03e91c4b2, DPU: 2)
2026-11-17T03:15:23.418Z [INFO] Connecting to catalog database 'lake_bronze'
2026-11-17T03:15:25.102Z [INFO] Ingesting partitioned parquet from s3://corporate-datalake-prod/raw/sales/2026-11-17/
2026-11-17T03:15:26.540Z [ERROR] Py4JJavaError / Python Worker Exception occurred:
Traceback (most recent call last):
  File "/tmp/runscript.py", line 48, in <module>
    main()
  File "/tmp/runscript.py", line 41, in main
    transformed_df = transform_sales_batch(records)
  File "/tmp/runscript.py", line 26, in transform_sales_batch
    "total_amount": float(record["quantity"]) * float(record["unit_price"]),
KeyError: 'unit_price'
2026-11-17T03:15:27.012Z [ERROR] Glue job execution failed with state FAILED.""",
        "original_code": """# AWS Glue PySpark ETL: Orders Bronze to Silver
import sys
from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext
from awsglue.context import GlueContext

def transform_sales_batch(records):
    transformed = []
    for record in records:
        cleaned = {
            "order_id": record["order_id"],
            "customer_id": record["customer_id"],
            "product_name": record["product_name"].strip().upper(),
            "quantity": int(record["quantity"]),
            # BUG: Upstream ERP changed column from 'unit_price' to 'price'
            "total_amount": float(record["quantity"]) * float(record["unit_price"]),
            "timestamp": record["timestamp"]
        }
        transformed.append(cleaned)
    return transformed

def main():
    records = [
        {"order_id": "1001", "customer_id": "C01", "product_name": "Laptop", "quantity": 1, "price": 1200.0, "timestamp": "2026-11-17T00:00:00Z"},
        {"order_id": "1002", "customer_id": "C02", "product_name": "Mouse ", "quantity": 2, "price": 25.5, "timestamp": "2026-11-17T01:10:00Z"}
    ]
    transformed = transform_sales_batch(records)
    print(f"Successfully processed {len(transformed)} order records.")

if __name__ == "__main__":
    main()
""",
        "rca_analysis": """### 🔍 Root Cause Analysis (RCA)

- **Failure Classification:** Upstream Schema Drift / Missing Dictionary Key (`KeyError: 'unit_price'`)
- **Fault Location:** Line 26 in function `transform_sales_batch`
- **Root Cause:** The script expects records to contain the dictionary key `"unit_price"`. However, the ingested data structure uses the column name `"price"`. As a result, direct dictionary subscripting `record["unit_price"]` raises an unhandled `KeyError`.
- **Impact:** Job `orders-bronze-to-silver` aborted, leaving downstream Silver data partitions unpopulated for daily reporting.
- **Recommended Fix Strategy:** Access the price field using `record["price"]` or defensively retrieve with fallback `record.get("price", record.get("unit_price", 0.0))`.
""",
        "diff_v1": """--- s3://corporate-datalake-prod/scripts/orders_bronze_silver.py
+++ s3://corporate-datalake-prod/gluehealer-versions/orders_bronze_silver/v1.py
@@ -23,7 +23,7 @@
             "product_name": record["product_name"].strip().upper(),
             "quantity": int(record["quantity"]),
-            # BUG: Upstream ERP changed column from 'unit_price' to 'price'
-            "total_amount": float(record["quantity"]) * float(record["unit_price"]),
+            # Healed: Safely access 'price' with backward-compatible fallback
+            "total_amount": float(record["quantity"]) * float(record.get("price", record.get("unit_price", 0.0))),
             "timestamp": record["timestamp"]
         }
""",
        "patched_code_v1": """# AWS Glue PySpark ETL: Orders Bronze to Silver
import sys
from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext
from awsglue.context import GlueContext

def transform_sales_batch(records):
    transformed = []
    for record in records:
        cleaned = {
            "order_id": record["order_id"],
            "customer_id": record["customer_id"],
            "product_name": record["product_name"].strip().upper(),
            "quantity": int(record["quantity"]),
            # Healed: Safely access 'price' with backward-compatible fallback
            "total_amount": float(record["quantity"]) * float(record.get("price", record.get("unit_price", 0.0))),
            "timestamp": record["timestamp"]
        }
        transformed.append(cleaned)
    return transformed

def main():
    records = [
        {"order_id": "1001", "customer_id": "C01", "product_name": "Laptop", "quantity": 1, "price": 1200.0, "timestamp": "2026-11-17T00:00:00Z"},
        {"order_id": "1002", "customer_id": "C02", "product_name": "Mouse ", "quantity": 2, "price": 25.5, "timestamp": "2026-11-17T01:10:00Z"}
    ]
    transformed = transform_sales_batch(records)
    print(f"Successfully processed {len(transformed)} order records.")

if __name__ == "__main__":
    main()
""",
        "diff_v2_feedback": """--- s3://corporate-datalake-prod/gluehealer-versions/orders_bronze_silver/v1.py
+++ s3://corporate-datalake-prod/gluehealer-versions/orders_bronze_silver/v2.py
@@ -23,8 +23,8 @@
             "quantity": int(record["quantity"]),
-            # Healed: Safely access 'price' with backward-compatible fallback
-            "total_amount": float(record["quantity"]) * float(record.get("price", record.get("unit_price", 0.0))),
+            # Reviewer requested: Coerce None to 0.0 and round total to 2 decimals
+            "total_amount": round(int(record.get("quantity") or 0) * float(record.get("price") or record.get("unit_price") or 0.0), 2),
             "timestamp": record["timestamp"]
         }
""",
        "execution_log_healed": """2026-11-17T03:16:10.198Z [INFO] Submitting retried Glue Job Run jr_9a22e8f1 with patched script v1.py
2026-11-17T03:16:14.331Z [INFO] Reading batch data from s3://corporate-datalake-prod/raw/sales/2026-11-17/
2026-11-17T03:16:16.892Z [INFO] Successfully processed 2 order records.
2026-11-17T03:16:17.401Z [INFO] Writing parquet partition to s3://corporate-datalake-prod/silver/orders/
2026-11-17T03:16:18.910Z [INFO] Job run jr_9a22e8f1 completed successfully with state SUCCEEDED."""
    },

    "ad_metrics_zero_division": {
        "id": "ad_metrics_zero_division",
        "title": "📊 AdTech Metrics Aggregator (ZeroDivisionError)",
        "job_name": "adtech-hourly-ctr-calc",
        "dpu": 4,
        "glue_type": "Spark Streaming",
        "cloudwatch_log_group": "/aws-glue/jobs/error",
        "job_run_id": "jr_41b7792c0a98f10e",
        "s3_original_path": "s3://adtech-analytics/scripts/calculate_ctr.py",
        "error_type": "ZeroDivisionError: division by zero",
        "summary": "Hourly campaign metrics calculation crashed because newly launched ad campaigns received zero impressions.",
        "raw_error_logs": """2026-11-17T14:00:10.891Z [INFO] Initializing PySpark Session on 4 G.1X DPUs
2026-11-17T14:00:18.234Z [INFO] Ingesting click & impression logs from Kafka sink
2026-11-17T14:00:21.099Z [ERROR] Py4JJavaError / Python Worker Exception:
Traceback (most recent call last):
  File "/tmp/calculate_ctr.py", line 42, in <module>
    main()
  File "/tmp/calculate_ctr.py", line 35, in main
    metrics = calculate_campaign_kpis(campaigns)
  File "/tmp/calculate_ctr.py", line 18, in calculate_campaign_kpis
    ctr = round((c["clicks"] / c["impressions"]) * 100, 2)
ZeroDivisionError: division by zero
2026-11-17T14:00:21.905Z [ERROR] Glue job execution failed with state FAILED.""",
        "original_code": """# Hourly AdTech Campaign Metrics
def calculate_campaign_kpis(campaigns):
    results = []
    for c in campaigns:
        # BUG: Newly activated campaigns have impressions == 0
        ctr = round((c["clicks"] / c["impressions"]) * 100, 2)
        results.append({
            "campaign_id": c["campaign_id"],
            "clicks": c["clicks"],
            "impressions": c["impressions"],
            "ctr_pct": ctr
        })
    return results

def main():
    campaigns = [
        {"campaign_id": "CAMP-01", "clicks": 140, "impressions": 5000},
        {"campaign_id": "CAMP-02", "clicks": 0, "impressions": 0}  # New campaign
    ]
    kpis = calculate_campaign_kpis(campaigns)
    print(f"Calculated KPIs for {len(kpis)} campaigns.")

if __name__ == "__main__":
    main()
""",
        "rca_analysis": """### 🔍 Root Cause Analysis (RCA)

- **Failure Classification:** Arithmetic Exception (`ZeroDivisionError: division by zero`)
- **Fault Location:** Line 18 in function `calculate_campaign_kpis`
- **Root Cause:** When newly scheduled campaigns launch, `impressions` starts at `0`. The formula `(clicks / impressions) * 100` attempts arithmetic division by zero without a defensive guard condition.
- **Impact:** Analytics dashboard feed halted; advertising bidding metrics delayed.
- **Recommended Fix Strategy:** Add a ternary guard: evaluate `ctr = round((c["clicks"] / c["impressions"]) * 100, 2) if c.get("impressions", 0) > 0 else 0.0`.
""",
        "diff_v1": """--- s3://adtech-analytics/scripts/calculate_ctr.py
+++ s3://adtech-analytics/gluehealer-versions/calculate_ctr/v1.py
@@ -15,4 +15,5 @@
     for c in campaigns:
-        # BUG: Newly activated campaigns have impressions == 0
-        ctr = round((c["clicks"] / c["impressions"]) * 100, 2)
+        # Healed: Guard against ZeroDivisionError for new campaigns with 0 impressions
+        impressions = c.get("impressions", 0)
+        ctr = round((c["clicks"] / impressions) * 100, 2) if impressions > 0 else 0.0
         results.append({
""",
        "patched_code_v1": """# Hourly AdTech Campaign Metrics
def calculate_campaign_kpis(campaigns):
    results = []
    for c in campaigns:
        # Healed: Guard against ZeroDivisionError for new campaigns with 0 impressions
        impressions = c.get("impressions", 0)
        ctr = round((c["clicks"] / impressions) * 100, 2) if impressions > 0 else 0.0
        results.append({
            "campaign_id": c["campaign_id"],
            "clicks": c["clicks"],
            "impressions": c["impressions"],
            "ctr_pct": ctr
        })
    return results

def main():
    campaigns = [
        {"campaign_id": "CAMP-01", "clicks": 140, "impressions": 5000},
        {"campaign_id": "CAMP-02", "clicks": 0, "impressions": 0}
    ]
    kpis = calculate_campaign_kpis(campaigns)
    print(f"Calculated KPIs for {len(kpis)} campaigns.")

if __name__ == "__main__":
    main()
""",
        "diff_v2_feedback": """--- s3://adtech-analytics/gluehealer-versions/calculate_ctr/v1.py
+++ s3://adtech-analytics/gluehealer-versions/calculate_ctr/v2.py
@@ -17,2 +17,3 @@
         impressions = c.get("impressions", 0)
-        ctr = round((c["clicks"] / impressions) * 100, 2) if impressions > 0 else 0.0
+        clicks = c.get("clicks", 0)
+        ctr = round((clicks / impressions) * 100, 2) if impressions > 0 else 0.0
""",
        "execution_log_healed": """2026-11-17T14:01:05.112Z [INFO] Submitting retried Glue Job Run jr_52d1108c with patched script v1.py
2026-11-17T14:01:12.780Z [INFO] Successfully calculated KPIs for 2 campaigns.
2026-11-17T14:01:14.291Z [INFO] Emitted metrics to CloudWatch: CAMP-01 (CTR: 2.8%), CAMP-02 (CTR: 0.0%)
2026-11-17T14:01:15.002Z [INFO] Job run completed successfully with state SUCCEEDED."""
    },

    "customer_type_error": {
        "id": "customer_type_error",
        "title": "👥 Customer 360 Sync (Corrupt Float Cast ValueError)",
        "job_name": "customer-profile-silver-sync",
        "dpu": 2,
        "glue_type": "Python Shell",
        "cloudwatch_log_group": "/aws-glue/python-jobs/output",
        "job_run_id": "jr_11bc90a84d33",
        "s3_original_path": "s3://customer-lake/scripts/sync_profiles.py",
        "error_type": "ValueError: could not convert string to float: 'N/A'",
        "summary": "Customer enrichment job crashed when parsing string placeholder 'N/A' into a numeric credit score column.",
        "raw_error_logs": """2026-11-17T09:42:15.112Z [INFO] Ingesting CSV updates from CRM ingest bucket
2026-11-17T09:42:18.991Z [INFO] Transforming customer profile records...
2026-11-17T09:42:19.450Z [ERROR] Fatal exception caught in pipeline:
Traceback (most recent call last):
  File "/tmp/sync_profiles.py", line 55, in <module>
    sync_profiles()
  File "/tmp/sync_profiles.py", line 34, in sync_profiles
    "credit_score": float(row["score"].strip())
ValueError: could not convert string to float: 'N/A'
2026-11-17T09:42:20.100Z [ERROR] Job halted with error code 1.""",
        "original_code": """# Customer 360 Bronze to Silver Sync
import csv

def sync_profiles():
    raw_customers = [
        {"id": "USR-101", "name": "Alice Miller", "score": "745.5"},
        {"id": "USR-102", "name": "Bob Vance", "score": "N/A"},  # BUG: Non-numeric string
        {"id": "USR-103", "name": "Charlie Day", "score": " 680.0 "}
    ]
    
    clean_profiles = []
    for row in raw_customers:
        clean_profiles.append({
            "user_id": row["id"],
            "name": row["name"],
            # BUG: crashes on 'N/A' or empty strings
            "credit_score": float(row["score"].strip())
        })
    return clean_profiles

if __name__ == "__main__":
    profiles = sync_profiles()
    print(f"Synced {len(profiles)} profiles.")
""",
        "rca_analysis": """### 🔍 Root Cause Analysis (RCA)

- **Failure Classification:** Data Quality / Dirty Input (`ValueError`)
- **Fault Location:** Line 34 in function `sync_profiles`
- **Root Cause:** Input CRM telemetry contains string placeholder values such as `'N/A'` or empty strings for missing score values. Direct invocation of `float(row["score"].strip())` fails on non-numeric strings.
- **Impact:** Customer profile sync failed, halting automated marketing audience segmentation.
- **Recommended Fix Strategy:** Implement a safe float parser function `def safe_float(val, default=None)` wrapped in a `try...except ValueError` block.
""",
        "diff_v1": """--- s3://customer-lake/scripts/sync_profiles.py
+++ s3://customer-lake/gluehealer-versions/sync_profiles/v1.py
@@ -3,2 +3,9 @@
 import csv
+
+def safe_float(val, default=0.0):
+    try:
+        return float(str(val).strip())
+    except (ValueError, TypeError):
+        return default
 
@@ -14,3 +21,3 @@
             "user_id": row["id"],
             "name": row["name"],
-            "credit_score": float(row["score"].strip())
+            "credit_score": safe_float(row.get("score"))
         })
""",
        "patched_code_v1": """# Customer 360 Bronze to Silver Sync
import csv

def safe_float(val, default=0.0):
    try:
        return float(str(val).strip())
    except (ValueError, TypeError):
        return default

def sync_profiles():
    raw_customers = [
        {"id": "USR-101", "name": "Alice Miller", "score": "745.5"},
        {"id": "USR-102", "name": "Bob Vance", "score": "N/A"},
        {"id": "USR-103", "name": "Charlie Day", "score": " 680.0 "}
    ]
    
    clean_profiles = []
    for row in raw_customers:
        clean_profiles.append({
            "user_id": row["id"],
            "name": row["name"],
            "credit_score": safe_float(row.get("score"))
        })
    return clean_profiles

if __name__ == "__main__":
    profiles = sync_profiles()
    print(f"Synced {len(profiles)} profiles.")
""",
        "diff_v2_feedback": """--- s3://customer-lake/gluehealer-versions/sync_profiles/v1.py
+++ s3://customer-lake/gluehealer-versions/sync_profiles/v2.py
@@ -4,3 +4,3 @@
-def safe_float(val, default=0.0):
+def safe_float(val, default=None):
     try:
""",
        "execution_log_healed": """2026-11-17T09:43:01.340Z [INFO] Submitting retried Python Shell Job Run jr_12cc88e1
2026-11-17T09:43:04.810Z [INFO] Successfully processed 3 customer profile records (1 defaulted).
2026-11-17T09:43:05.120Z [INFO] Written to Silver Delta table at s3://customer-lake/silver/customers/
2026-11-17T09:43:05.900Z [INFO] Job run completed successfully with state SUCCEEDED."""
    },

    "oom_memory_exhaustion": {
        "id": "oom_memory_exhaustion",
        "title": "🔥 Clickstream PySpark ETL (YARN Out-Of-Memory Auto-Tuning)",
        "job_name": "clickstream-hourly-enrichment",
        "dpu": 2,
        "glue_type": "Spark Streaming / Large Batch",
        "cloudwatch_log_group": "/aws-glue/jobs/error",
        "job_run_id": "jr_77de8812c3f4",
        "s3_original_path": "s3://adtech-datalake/scripts/clickstream_enrichment.py",
        "error_type": "Container killed by YARN for exceeding memory limits (Exit code 137)",
        "summary": "Heavy traffic burst during flash sale campaign overwhelmed executor memory during shuffle partition join, triggering exit code 137.",
        "raw_error_logs": """2026-11-18T05:10:14.120Z [INFO] Initializing AWS Glue Spark Session on 2 G.1X Workers (16 GB RAM per executor)
2026-11-18T05:10:20.450Z [INFO] Reading 8.5 GB micro-batch from Kafka raw partition...
2026-11-18T05:10:25.890Z [WARN] MemoryConsumer: Spark shuffle memory spilled 4.2 GB to disk
2026-11-18T05:10:28.110Z [ERROR] Container killed by YARN for exceeding memory limits: 16.0 GB of 16.0 GB physical memory used.
2026-11-18T05:10:28.115Z [ERROR] ExecutorLostFailure (executor 1 exited with exit code 137, Reason: Container killed by YARN for exceeding memory limits)
2026-11-18T05:10:29.001Z [ERROR] Glue job execution failed with state FAILED.""",
        "original_code": """# PySpark Clickstream Enrichment Job
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, window

def run_enrichment():
    spark = SparkSession.builder.appName("ClickstreamEnrichment").getOrCreate()
    
    # 8.5 GB micro-batch with skewed join keys
    raw_df = spark.read.parquet("s3://adtech-datalake/raw/clickstream/")
    dim_users = spark.read.parquet("s3://adtech-datalake/dims/users/")
    
    # Skewed wide shuffle join causes memory spike
    enriched = raw_df.join(dim_users, on="device_id", how="inner")
    enriched.write.mode("overwrite").parquet("s3://adtech-datalake/silver/clickstream/")

if __name__ == "__main__":
    run_enrichment()
""",
        "rca_analysis": """### 🔍 Root Cause Analysis (Infrastructure Bottleneck)

- **Failure Classification:** Infrastructure / Hardware Resource Exhaustion (`OOM / YARN Kill 137`)
- **Fault Location:** AWS Glue Execution Layer (Worker Allocation: `WorkerType: G.1X`, 2 Workers)
- **Root Cause:** A 4x traffic surge caused partition shuffle operations to exceed the 16 GB heap ceiling per executor. Code logic is 100% correct; failure is strictly memory-bound.
- **Fix Strategy (Zero Code Changes):** Auto-tune AWS Glue resources:
  - Upgrade `WorkerType` from `G.1X` (16 GB) ➔ `G.2X` (32 GB RAM per executor).
  - Scale `NumberOfWorkers` from 2 ➔ 4 to parallelize partition shuffles and eliminate disk spill.
""",
        "diff_v1": """--- Current AWS Glue Job Configuration
+++ Auto-Tuned Resource Configuration
- WorkerType: G.1X (4 vCPU, 16 GB RAM per executor)
+ WorkerType: G.2X (8 vCPU, 32 GB RAM per executor) [2x Memory Ceiling Allocated]
- NumberOfWorkers: 2
+ NumberOfWorkers: 4 [Horizontal Parallelism Scale Factor]
""",
        "patched_code_v1": """# PySpark Clickstream Enrichment Job (Code untouched - Resources auto-tuned to G.2X / 4 Workers)
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, window

def run_enrichment():
    spark = SparkSession.builder.appName("ClickstreamEnrichment").getOrCreate()
    
    raw_df = spark.read.parquet("s3://adtech-datalake/raw/clickstream/")
    dim_users = spark.read.parquet("s3://adtech-datalake/dims/users/")
    
    enriched = raw_df.join(dim_users, on="device_id", how="inner")
    enriched.write.mode("overwrite").parquet("s3://adtech-datalake/silver/clickstream/")

if __name__ == "__main__":
    run_enrichment()
""",
        "diff_v2_feedback": """--- Current AWS Glue Job Configuration
+++ Auto-Tuned Resource Configuration (Reviewer Adjusted)
- WorkerType: G.1X
+ WorkerType: G.2X
- NumberOfWorkers: 2
+ NumberOfWorkers: 6 [Additional partition parallelism requested]
""",
        "execution_log_healed": """2026-11-18T05:11:02.120Z [INFO] Submitting retried Glue Job Run with auto-tuned resources: WorkerType=G.2X, NumberOfWorkers=4
2026-11-18T05:11:15.890Z [INFO] Processing 8.5 GB micro-batch on 4 G.2X workers (32 GB RAM each)
2026-11-18T05:11:21.002Z [INFO] Shuffle completed with ZERO disk spill.
2026-11-18T05:11:22.450Z [INFO] Job run completed successfully with state SUCCEEDED."""
    }
}
