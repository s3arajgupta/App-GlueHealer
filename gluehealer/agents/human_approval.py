"""
Human Approval Agent

Presents the patch to the user via CLI and collects approve/reject decisions.
On rejection, captures feedback so the RCA agent can adjust.
Supports reviewing both code diffs and auto-tuned infrastructure configurations (OOM / timeouts).
"""
from ..state import HealerState


def human_approval(state: HealerState) -> dict:
    retry = state.get("retry_count", 0)
    max_r = state.get("max_retries", 3)
    is_infra = state.get("failure_category") == "infrastructure"

    print()
    print("=" * 70)
    print("🩹  GLUEHEALER PATCH REVIEW")
    print("=" * 70)
    print(f"  Job:      {state['job_name']}")
    print(f"  Category: {'Infrastructure / Resource Auto-Tuning' if is_infra else 'Code Bug'}")
    print(f"  Attempt:  {retry + 1} / {max_r}")
    print()
    print("--- Root Cause Analysis " + "-" * 46)
    print(state["rca_result"])
    print()
    if is_infra:
        print("--- Auto-Tuned Infrastructure Configuration " + "-" * 26)
    else:
        print("--- Proposed Patch (unified diff) " + "-" * 36)
    print(state["patch_display"])
    print("=" * 70)

    if state.get("auto_approve"):
        print("\n  ⚡ Auto-approving patch (--auto-approve enabled)")
        return {"status": "approved", "human_feedback": ""}

    while True:
        try:
            choice = input("\n  [A]pprove  [R]eject  [V]iew full content  > ").strip().lower()
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
            if is_infra:
                print("--- Proposed Glue Configuration Parameters " + "-" * 27)
                print(f"Proposed: {state.get('proposed_job_config')}")
                print(f"Baseline: {state.get('current_job_config')}")
            else:
                print("--- Corrected Script " + "-" * 49)
                print(state["corrected_script"])
            print("-" * 70)

        else:
            print("  Please enter 'a', 'r', or 'v'.")
