"""
Patch Generator Agent

Calls the LLM to produce the corrected script based on the RCA output.
Also computes a unified diff for human review.
"""
import difflib
import re
from ..state import HealerState
from ..config import chat_completion


def _strip_markdown_fences(text: str) -> str:
    """Extract Python code from markdown fences if present, otherwise clean up text."""
    match = re.search(r"```(?:python)?\s*\n(.*?)\n```", text, re.DOTALL)
    if match:
        return match.group(1).strip()

    lines = text.strip().splitlines()
    if lines and lines[0].strip().startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip().startswith("```"):
        lines = lines[:-1]
    return "\n".join(lines).strip()


def patch_generator(state: HealerState) -> dict:
    print("🩹 Patch Generator: calling LLM to generate corrected script...", flush=True)

    raw = chat_completion([
        {
            "role": "system",
            "content": (
                "You are an expert code repair agent. "
                "Generate the COMPLETE corrected Python script. "
                "Output ONLY valid Python code — no markdown fences, "
                "no explanations, no commentary. "
                "The output must be directly executable."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Fix this script based on the root cause analysis below.\n\n"
                f"## Original Script\n```python\n{state['script_content']}\n```\n\n"
                f"## Root Cause Analysis\n{state['rca_result']}\n\n"
                "Output the complete corrected Python script. "
                "No markdown, no explanations — just the code."
            ),
        },
    ])

    corrected = _strip_markdown_fences(raw)

    # Compute unified diff for human review
    orig_lines = state["script_content"].splitlines(keepends=True)
    fix_lines = corrected.splitlines(keepends=True)
    diff = difflib.unified_diff(
        orig_lines,
        fix_lines,
        fromfile="original",
        tofile="patched",
    )
    patch_display = "".join(diff)

    if not patch_display:
        patch_display = "(no visible diff — LLM returned identical code)"

    print("   ✅ Patch generated")

    return {
        "corrected_script": corrected,
        "patch_display": patch_display,
        "status": "patch_ready",
    }
