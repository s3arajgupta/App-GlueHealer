"""
Context Builder Agent

Gathers all context the downstream agents need:
  - Current script content (re-read each cycle in case a patch was applied)
  - Error logs (carried forward from the last run)
  - Historical patches from LangGraph state
"""
from ..state import HealerState
from ..tools.interface import ScriptStore


def context_builder(state: HealerState, script_store: ScriptStore) -> dict:
    script_content = script_store.read_script(state["script_path"])

    print(f"\n📋 Context Builder: read script ({len(script_content)} chars)")
    if state.get("historical_patches"):
        print(f"   History: {len(state['historical_patches'])} previous patch(es)")
    if state.get("human_feedback"):
        print(f"   Reviewer feedback: \"{state['human_feedback']}\"")

    return {
        "script_content": script_content,
        "status": "analyzing",
    }
