# 🗺️ GlueHealer — Project Phase Plan & Architecture Vision

> **Vision**: An autonomous, self-healing agentic system that continuously detects, analyzes, patches, and verifies failing AWS Glue ETL jobs — eliminating tedious on-call triage while maintaining strict human-in-the-loop safety and zero destructive changes.

---

## 🎯 Executive Summary & Core Principles

1. **Safety First (Zero Destructive Overwrites)**: Original ETL scripts are never modified in place. All changes are written as versioned artifacts (`v1`, `v2`, `v3`) with immediate rollback capability.
2. **Self-Correcting Cyclic Feedback**: Rejections and failed retries do not restart blindly — they route back through the **Context Builder** with cumulative history, preventing the LLM from repeating ineffective fixes.
3. **Hybrid Abstraction**: The core multi-agent reasoning is decoupled from cloud infrastructure through unified interfaces (`ScriptStore`, `JobRunner`), enabling \$0 local testing before touching cloud credits.
4. **Human-in-the-Loop Gate**: Autonomous diagnosis and patch generation paired with explicit human authorization before deploying to production.

---

## ☁️ AWS Services Needed for Phase 2

For Phase 2 (AWS Integration), GlueHealer interacts with four core AWS services:

| AWS Service | Resource / API | Role in GlueHealer | Cost Impact on \$100 Credits |
|---|---|---|---|
| **AWS Glue** | `StartJobRun`, `GetJobRun`, `GetJob` | Runs the ETL scripts and returns job state | **Main Cost Driver** (~$0.05–$0.15 per short 2-DPU run). *Optimized via Python Shell jobs or minimal DPUs.* |
| **Amazon S3** | `s3:GetObject`, `s3:PutObject` | Stores original scripts, input data, and versioned patched scripts | Negligible (<$0.01/month) |
| **Amazon CloudWatch Logs** | `logs:FilterLogEvents`, `logs:GetLogEvents` | Automatically ingests stack traces from `/aws-glue/jobs/error` | Negligible (<$0.01) |
| **AWS IAM** | Service Role & User Credentials | Grants Glue execution access to S3/logs, and gives GlueHealer CLI access | Free |
| **Amazon EventBridge** *(Optional)* | Glue Job State Change Rule | Notifies GlueHealer whenever a job enters `FAILED` state | Free (under free tier) |

---

## 🧭 Master Phasing Roadmap

```
┌────────────────────────────────────────────────────────┐
│  PHASE 1: Local Agent Engine & Cyclic Graph           │  ✅ COMPLETED
│  • LangGraph / Cyclic State Machine Workflow           │
│  • Context Builder, RCA Analyzer, Patch Generator      │
│  • Human Approval Agent & Versioned Apply Patch        │
│  • Local Filesystem Store & Subprocess Runner          │
│  • End-to-end verified on sample broken ETL jobs       │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│  PHASE 2: AWS Cloud Backend Integration               │  ✅ COMPLETED
│  • AWS Boto3 Tool Implementations (tools/aws/)        │
│  • S3 Script Store (s3:// bucket script versioning)    │
│  • CloudWatch Error Log Fetcher (Glue log groups)      │
│  • AWS Glue Job Runner (StartJobRun + status polling)  │
│  • Full CLI integration (python -m gluehealer --aws)   │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│  PHASE 3: Interactive Visual Approval Dashboard        │  ✅ COMPLETED
│  • Streamlit Web Application (gluehealer/ui/app.py)    │
│  • Rich mock scenarios (Schema drift, ZeroDiv, TypeErr)│
│  • Side-by-side & unified syntax-highlighted diff      │
│  • One-click Approve / Reject with Feedback loopback   │
│  • Offline CLI Demo Mode (python -m gluehealer demo)   │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│  PHASE 4: Autonomous Triggers, Rollback & OOM Healing  │  🛡️
│  • EventBridge Event-Driven Healing Trigger            │
│  • Infrastructure / OOM Healing (DPU & memory tweaks)  │
│  • One-click CLI/UI Rollback Command                   │
│  • Observability metrics dashboard                     │
└────────────────────────────────────────────────────────┘
```

---

## 📌 Detailed Checkpoints & Deliverables

### ✅ Phase 1: Local Agent Engine & Cyclic Graph (Completed)
- [x] **State Schema Definition (`gluehealer/state.py`)**: Typed state tracking job identity, script content, error logs, RCA analysis, diffs, human feedback, retry counts, and patch history.
- [x] **Tool Abstraction Layer (`gluehealer/tools/interface.py`)**: Abstract base classes `ScriptStore` and `JobRunner`.
- [x] **Local Tool Implementations (`gluehealer/tools/local/`)**:
  - `LocalScriptStore`: Reads original scripts, saves versioned snapshots (`job_versions/<job>/v<N>.py`), and copies companion assets.
  - `LocalJobRunner`: Executes scripts in isolated subprocesses with timeouts and stdout/stderr capture.
- [x] **Modular Agent Nodes (`gluehealer/agents/`)**:
  - `context_builder`: Ingests latest code, logs, and historical patches.
  - `rca_analyzer`: Diagnoses root cause, precise line numbers, and fix strategy.
  - `patch_generator`: Outputs executable Python code and computes unified diff.
  - `human_approval`: Interactive CLI prompt (`[A]pprove`, `[R]eject`, `[V]iew`) + `--auto-approve` flag.
  - `apply_patch`: Creates non-destructive versioned scripts.
  - `retry_runner`: Evaluates rerun results, handles `healed`, `failed` loopback, and `escalated` exit.
- [x] **Cyclic Orchestrator (`gluehealer/graph.py`)**: Zero-native-dependency graph executor ensuring graceful loopback to Context Builder.
- [x] **Verified Test Cases**:
  - `broken_etl.py`: Resolved `KeyError: 'unit_price'` → `record['price']` in 1 attempt.
  - `broken_transform.py`: Fixed both `is_active` KeyError and `sessions == 0` ZeroDivisionError in 1 attempt.

---

### ✅ Phase 2: AWS Cloud Backend Integration (Completed)
**Objective**: Enable GlueHealer to heal actual AWS Glue jobs running in your AWS account using minimal cloud credits.

#### Checkpoint 2.1: AWS Tool Implementations (`gluehealer/tools/aws/`) ✅
- [x] **`gluehealer/tools/aws/s3_store.py` (`S3ScriptStore`)**:
  - Parses S3 URIs (`s3://bucket/prefix/job.py`).
  - Downloads script for analysis via `boto3.client('s3')`.
  - Non-destructive S3 versioning (`s3://bucket/gluehealer-versions/<job>/v<N>.py`).
- [x] **`gluehealer/tools/aws/cloudwatch_logs.py` (`CloudWatchLogFetcher`)**:
  - Automatically identifies the Glue log stream: `/aws-glue/jobs/error` or `/aws-glue/python-jobs/output` for `JobRunId`.
  - Filters out Spark noise and extracts the fatal exception / stack trace.
- [x] **`gluehealer/tools/aws/glue_runner.py` (`GlueJobRunner`)**:
  - Queries job configuration (`get_job`) and automatically identifies the latest failed run (`get_latest_failed_run`).
  - Updates job definition `Command.ScriptLocation` pointing safely to the versioned S3 script.
  - Invokes `glue.start_job_run(JobName=...)` and polls with backoff until `SUCCEEDED` or `FAILED`.
- [x] **CLI AWS Mode Integration (`gluehealer/__main__.py`)**:
  - `python -m gluehealer --aws --job-name <job_name>` connects the entire LangGraph workflow directly to AWS.

#### Checkpoint 2.2: IAM & Security Configuration
- [x] Credential configuration via `.env` (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION`, `AWS_PROFILE`).
- [x] Least-privilege IAM requirements: `s3:GetObject`, `s3:PutObject`, `logs:DescribeLogStreams`, `logs:GetLogEvents`, `glue:GetJob`, `glue:GetJobRuns`, `glue:UpdateJob`, `glue:StartJobRun`.

#### Checkpoint 2.3: Targeted Cloud Validation
- [x] AWS tool test suite implemented in `tests/test_aws_adapters.py` (URI parsing, Spark noise filtration, all passing).
- [x] CLI flag validation and graceful error messaging for missing AWS credentials.

---

### 🎨 Phase 3: Interactive Visual Approval Dashboard
**Objective**: Replace CLI prompts with an intuitive developer web dashboard.

#### Services & Technologies Required for Phase 3:
| Component / Service | Purpose | Hosting & Cost Profile |
|---|---|---|
| **Streamlit (Python)** | Frontend dashboard interface hooking directly into `HealerState` & `graph.py` | Local development (`localhost:8501`) = **$0** |
| **Monaco / Diff Viewer** | Syntax-highlighted side-by-side or unified green/red diff comparisons | Embedded client component |
| **AWS App Runner / ECS Fargate** *(Optional Cloud Hosting)* | Containerized hosting of the Streamlit app behind managed HTTPS | ~$5–$10/month (or run on-demand only) |
| **Amazon EC2 (t4g.small / t3.micro)** *(Alternative Cloud Hosting)* | Low-cost virtual machine hosting Streamlit behind Nginx | Covered under Free Tier or ~$3–$5/month |
| **Amazon Cognito** *(Optional Security)* | Role-based user authentication (SSO/OAuth) so only authorized data engineers can approve patches | Free Tier (first 50,000 MAUs free) |
| **Amazon DynamoDB** *(Optional Audit)* | Audit log recording who approved/rejected each patch, reviewer notes, and timestamps | Free Tier (25 GB free forever) |

#### Checkpoint 3.1: Streamlit Web UI (`gluehealer/ui/app.py`) ✅
- [x] **Zero-Setup Simulation Mode**: 3 authentic enterprise failure scenarios (Schema Drift `KeyError`, Metrics `ZeroDivisionError`, Cast `ValueError`).
- [x] **Job Overview & CloudWatch Log Viewer**: Real-time stack trace inspection for failed Glue runs.
- [x] **Root Cause Card**: Formatted diagnosis explaining why the failure occurred with recommended fix strategy.
- [x] **Visual Diff Viewer**: Color-coded unified diff view showing removals in red and additions in green.
- [x] **Human Approval Gate**:
  - [x] Big green `Approve & Deploy Patch` button.
  - [x] Red `Reject & Request Revision` button with feedback input text box that loops back to Context Builder.
- [x] **Execution Timeline & Audit**: Visual tracker showing Attempt 1 → Human Critique → Attempt 2 → Healed.
- [x] **CLI Offline Demo**: `python -m gluehealer demo` runs zero-API instant demonstration.

---

### 🛡️ Phase 4: Autonomous Monitoring, Rollback & Infrastructure Healing
**Objective**: Production-grade automation, infrastructure adjustments, and safety tooling.

#### Services & Technologies Required for Phase 4:
| AWS Service | What It Does in GlueHealer | Cost Profile |
|---|---|---|
| **Amazon EventBridge** | **Automated Event Trigger**: Detects when any Glue job enters `state: FAILED` and triggers GlueHealer without polling. | **Free** (default service event bus is free) |
| **AWS Lambda / Step Functions** | **Serverless Orchestrator**: Executes Context Builder + RCA agent headlessly in response to failure events without needing a 24/7 server. | **Free** (under 1M free Lambda invocations/month) |
| **Amazon SNS / Slack Webhooks** | **Approval Notifications**: Sends alerts: *"Glue job `sales_daily` failed. GlueHealer generated a patch with 95% confidence. [Click to review]"*. | **Free** (SNS free tier covers 1,000 emails/month) |
| **AWS Glue (Config APIs)** | **Infrastructure & OOM Healing**: Uses `glue:UpdateJob` / `start_job_run` to scale DPUs, change `WorkerType` (`G.1X` → `G.2X`), or adjust Spark shuffle memory. | Pay only when the job re-runs |
| **Amazon CloudWatch Metrics** | **Observability Dashboard**: Custom metrics tracking MTTR (Mean Time to Resolution), patch acceptance rate, autonomous healing rate, and DPU costs. | Free Tier (up to 10 custom metrics free) |
| **Amazon S3 (Versioning & Rollback)** | **One-Click Rollback Storage**: Maintains a metadata manifest (`metadata.json`) pointing to historical S3 keys for instant restoration. | Negligible (<$0.01) |

#### Phase 4 End-to-End Autonomous Architecture Flow:
```
   AWS Glue Job Fails (e.g. OOM or KeyError)
                      │
                      ▼
             Amazon EventBridge
         (Captures "FAILED" event)
                      │
                      ▼
             AWS Lambda / Runner
           (Runs Context Builder + RCA)
                      │
                      ▼
         Amazon SNS / Slack Webhook
   ("Patch Ready! Click to review in Streamlit")
                      │
                      ▼
             Data Engineer Reviews
            (Approve / Reject in UI)
                      │
                      ▼
   AWS Glue Re-run + CloudWatch Metrics Logged
```

#### Checkpoint 4.1: Configuration & OOM Self-Healing
- Some Glue failures are not code bugs, but resource exhaustion:
  - `OutOfMemoryError: Java heap space`
  - `Container killed by YARN for exceeding memory limits`
- RCA Agent learns to diagnose hardware/configuration bottlenecks and propose job parameter updates:
  - Adjusting `WorkerType` (e.g. `G.1X` → `G.2X`)
  - Increasing `NumberOfWorkers`
  - Extending `Timeout` parameter

#### Checkpoint 4.2: One-Click Rollback Command
- `python -m gluehealer rollback --job-name <job> --to-version v1`
- Reverts the Glue job definition or active S3 pointer immediately if downstream issues emerge.

#### Checkpoint 4.3: EventBridge Event-Driven Automation
- EventBridge rule listening to:
  ```json
  {
    "source": ["aws.glue"],
    "detail-type": ["Glue Job State Change"],
    "detail": { "state": ["FAILED"] }
  }
  ```
- Automatically triggers a Lambda or container running GlueHealer in notification/draft mode, paging engineers only when the patch is ready for approval.

---

## 💰 University Credit Budget Allocation (\$100 Total)

| Phase / Activity | Expected AWS Spend | Notes |
|---|---|---|
| **Phase 1: Local Engine** | **\$0.00** | Uses local subprocesses & filesystem |
| **Phase 2: Cloud Testing & Iteration** | **\$8.00 – \$12.00** | Run 10–15 short test jobs (2 DPUs for 2 mins each) |
| **Phase 3 & 4: Demos & Recordings** | **\$5.00 – \$8.00** | Live showcase runs for presentation or portfolio |
| **Remaining Student Reserve** | **\$80.00+** | Safely preserved for coursework and other projects |

---

## ⌨️ Command Quick Reference (Active & Ready to Use)

| Purpose | Command | Notes |
|---|---|---|
| **Streamlit Interactive UI** | `streamlit run gluehealer/ui/app.py` or `python -m gluehealer.ui` | Visual dashboard with simulation scenarios & live script runner |
| **Offline Showcase Demo** | `python -m gluehealer demo --auto-approve` | 0.5s execution, no AWS / API keys needed |
| **Local Script Self-Healing** | `python -m gluehealer sample_jobs/broken_etl.py` | Local execution with interactive human approval prompt |
| **Local Auto-Approve Healing** | `python -m gluehealer sample_jobs/broken_etl.py --auto-approve` | Runs local healing pipeline without interactive prompts |
| **AWS Cloud Healing (Latest Failure)** | `python -m gluehealer --aws --job-name <glue_job_name>` | Ingests CloudWatch logs, patches S3, retries Glue job |
| **AWS Cloud Healing (Specific Run)** | `python -m gluehealer --aws --job-name <job_name> --run-id <jr_xxx>` | Triages a specific historical failed run |
| **Run Pytest Test Suite** | `pytest tests/ -v` | Verifies AWS adapters & state machine transitions |

---

## 🏁 Definition of Done for Entire Project

The GlueHealer project reaches full maturity when:
1. A developer or automated event can point to any failed AWS Glue job run ID.
2. The agent pipeline autonomously extracts logs, diagnoses the root cause, and generates a clean diff.
3. The engineer can review and approve the patch in a single click via CLI or Streamlit UI.
4. The system updates the job version in S3, triggers a rerun, verifies success, and records telemetry — all without overwriting original assets.
