"""
Human Approval Agent

Presents the patch to the user via CLI and collects approve/reject decisions.
On rejection, captures feedback so the RCA agent can adjust.
"""
from ..state import HealerState


def human_approval(state: HealerState) -> dict:
    retry = state.get("retry_count", 0)
    max_r = state.get("max_retries", 3)

    print()
    print("=" * 70)
    print("🩹  PATCH REVIEW")
    print("=" * 70)
    print(f"  Job:      {state['job_name']}")
    print(f"  Attempt:  {retry + 1} / {max_r}")
    print()
    print("--- Root Cause Analysis " + "-" * 46)
    print(state["rca_result"])
    print()
    print("--- Proposed Patch (unified diff) " + "-" * 36)
    print(state["patch_display"])
    print("=" * 70)

    if state.get("auto_approve"):
        print("\n  ⚡ Auto-approving patch (--auto-approve enabled)")
        return {"status": "approved", "human_feedback": ""}

    while True:
        try:
            choice = input("\n  [A]pprove  [R]eject  [V]iew full corrected script  > ").strip().lower()
        except EOFError:
            print("\n  (EOF received, defaulting to approve)")
            return {"status": "approved", "human_feedback": ""}

        if choice in ("a", "approve"):
            print("  ✅ Patch approved")
            return {"status": "approved", "human_feedback": ""}

        elif choice in ("r", "reject"):
            feedback = input("  Reason for rejection: ").strip()
            print("  ❌ Patch rejected")
            return {"status": "rejected", "human_feedback": feedback}

        elif choice in ("v", "view"):
            print()
            print("--- Corrected Script " + "-" * 49)
            print(state["corrected_script"])
            print("-" * 70)

        else:
            print("  Please enter 'a', 'r', or 'v'.")
