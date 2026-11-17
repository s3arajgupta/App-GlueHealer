"""
RCA / Error Analyzer Agent

Calls the LLM to perform root cause analysis on the failed job.
Classifies failures into:
  - CODE_BUG: Logic, syntax, schema drift, type errors
  - INFRASTRUCTURE_BOTTLENECK: Out-of-memory (OOM), YARN container kills, timeouts
"""
from ..state import HealerState
from ..config import chat_completion

INFRA_PATTERNS = [
    "outofmemoryerror",
    "exceeding memory limits",
    "exit code 137",
    "exit code 143",
    "executorlostfailure",
    "job run timeout",
    "timeoutexception",
    "overhead limit exceeded",
    "killed by yarn",
    "java heap space",
]


def rca_analyzer(state: HealerState) -> dict:
    error_logs = state.get("error_logs", "")

    # Classify failure category
    is_infra = any(p in error_logs.lower() for p in INFRA_PATTERNS)
    category = "infrastructure" if is_infra else "code"

    # Build history context
    history_ctx = ""
    patches = state.get("historical_patches", [])
    if patches:
        history_ctx = "\n\n## Previous Patch Attempts\n"
        for i, p in enumerate(patches, 1):
            history_ctx += (
                f"\n### Attempt {i}\n"
                f"- Patch summary: {p['patch_summary']}\n"
                f"- Outcome: {p['outcome']}\n"
            )
            if p.get("feedback"):
                history_ctx += f"- Human feedback: {p['feedback']}\n"
        history_ctx += (
            "\nDo NOT repeat a fix that already failed. "
            "Try a different approach.\n"
        )

    # Build rejection feedback context
    feedback_ctx = ""
    if state.get("human_feedback"):
        feedback_ctx = (
            "\n\n## Reviewer Feedback (patch was REJECTED)\n"
            f"{state['human_feedback']}\n"
            "Address this feedback in your new analysis.\n"
        )

    print("🔍 RCA Analyzer: calling LLM for root cause analysis...", flush=True)

    if state.get("demo_mode"):
        if is_infra:
            rca = (
                "### 1. Root Cause (Infrastructure Bottleneck: Out-Of-Memory)\n"
                "The Spark worker container was killed by YARN (exit code 137) after exceeding memory limits. "
                "The active worker type (G.1X) provides 16 GB of RAM, which was fully exhausted during "
                "partition shuffle operations.\n\n"
                "### 2. Location\n"
                "Infrastructure: AWS Glue Execution Layer (WorkerType: G.1X, NumberOfWorkers: 2)\n\n"
                "### 3. Fix Strategy\n"
                "Auto-tune Glue resource configuration: upgrade WorkerType from G.1X (16 GB) to G.2X (32 GB RAM per executor) "
                "and scale NumberOfWorkers from 2 to 4 to eliminate shuffle spill and memory exhaustion without altering script logic."
            )
        else:
            rca = (
                "### 1. Root Cause\n"
                "KeyError: 'unit_price' occurred because the input CSV schema uses header 'price' instead of 'unit_price'.\n\n"
                "### 2. Location\n"
                "Line 30: record['unit_price']\n\n"
                "### 3. Fix Strategy\n"
                "Update dictionary indexing from record['unit_price'] to record['price']."
            )
        print(f"   ✅ RCA complete ({category} failure, demo mode)", flush=True)
        return {"rca_result": rca, "failure_category": category}

    rca = chat_completion([
        {
            "role": "system",
            "content": (
                "You are an expert data engineer and AWS Glue performance architect. "
                "Analyze the error output to identify the root cause precisely. "
                "Classify whether the failure is a CODE BUG (schema drift, syntax, type error) "
                "or an INFRASTRUCTURE BOTTLENECK (OOM, YARN container killed, timeout, memory overhead). "
                "If it is an infrastructure bottleneck, recommend resource tuning (WorkerType G.1X -> G.2X, workers, timeouts)."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Analyze this failed ETL job and identify the root cause.\n\n"
                f"## Script\n```python\n{state.get('script_content', '')}\n```\n\n"
                f"## Error Output\n```\n{error_logs}\n```\n"
                f"{history_ctx}{feedback_ctx}\n"
                "Provide:\n"
                "1. **Root cause** — what failed and whether it is a code bug or infrastructure bottleneck\n"
                "2. **Location** — specific line/function OR Glue worker/memory parameters\n"
                "3. **Fix strategy** — code repair OR resource auto-tuning recommendations\n"
            ),
        },
    ])

    print(f"   ✅ RCA complete ({category} failure)")
    return {"rca_result": rca, "failure_category": category}
