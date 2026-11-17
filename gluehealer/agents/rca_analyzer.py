"""
RCA / Error Analyzer Agent

Calls the LLM to perform root cause analysis on the failed job.
Takes into account:
  - The script source code
  - The error output
  - Any historical patch attempts and their outcomes
  - Human feedback from rejected patches
"""
from ..state import HealerState
from ..config import chat_completion


def rca_analyzer(state: HealerState) -> dict:
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
        rca = (
            "### 1. Root Cause\n"
            "KeyError: 'unit_price' occurred because the input CSV schema uses header 'price' instead of 'unit_price'.\n\n"
            "### 2. Location\n"
            "Line 30: record['unit_price']\n\n"
            "### 3. Fix Strategy\n"
            "Update dictionary indexing from record['unit_price'] to record['price']."
        )
        print("   ✅ RCA complete (demo mode)", flush=True)
        return {"rca_result": rca}

    rca = chat_completion([
        {
            "role": "system",
            "content": (
                "You are an expert data engineer specializing in ETL pipeline debugging. "
                "Analyze the error and identify the root cause precisely. "
                "Consider both code-level bugs AND configuration issues "
                "(memory, timeouts, permissions, missing dependencies)."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Analyze this failed ETL job and identify the root cause.\n\n"
                f"## Script\n```python\n{state['script_content']}\n```\n\n"
                f"## Error Output\n```\n{state['error_logs']}\n```\n"
                f"{history_ctx}{feedback_ctx}\n"
                "Provide:\n"
                "1. **Root cause** — what exactly went wrong\n"
                "2. **Location** — specific line(s) and function(s)\n"
                "3. **Fix strategy** — exactly how to fix it\n"
            ),
        },
    ])

    print("   ✅ RCA complete")
    return {"rca_result": rca}
