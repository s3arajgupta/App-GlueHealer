"""
GlueHealer State-Machine Workflow

A lightweight graph executor that implements the same cyclic workflow
as LangGraph but with zero native dependencies. The state dict flows
through nodes, and conditional routing functions decide the next node.

Flow:
  context_builder → rca_analyzer → patch_generator → human_approval
       ↑                                                  │
       │  (rejected)──────────────────────────────────────┘
       │                                        (approved)↓
       │                                           apply_patch
       │                                                  │
       │                                           retry_runner
       │  (failed)────────────────────────────────────────┘
       └──────────────────────────────────────────────────┘
                                                 (healed | escalated) → END

When LangGraph is available (production / no DLL restrictions), this
module can be swapped for a full LangGraph implementation — the agent
functions are identical.
"""
from __future__ import annotations

from typing import Callable

from .state import HealerState
from .tools.local import LocalScriptStore, LocalJobRunner
from .agents import (
    context_builder,
    rca_analyzer,
    patch_generator,
    human_approval,
    apply_patch,
    retry_runner,
)

# Sentinel
END = "__end__"


# ── Routing functions ──────────────────────────────────────────────

def _route_approval(state: HealerState) -> str:
    return "apply_patch" if state["status"] == "approved" else "context_builder"


def _route_retry(state: HealerState) -> str:
    status = state["status"]
    if status == "healed":
        return END
    if status == "escalated":
        return END
    return "context_builder"  # failed → loop back


# ── Graph definition ───────────────────────────────────────────────

def build_graph(
    script_store: LocalScriptStore | None = None,
    job_runner: LocalJobRunner | None = None,
):
    """
    Build and return a compiled graph (a callable that accepts and
    returns HealerState).
    """
    store = script_store or LocalScriptStore()
    runner = job_runner or LocalJobRunner()

    # Node name → (node_fn, next)
    # next is either a string (unconditional) or a routing callable
    nodes: dict[str, tuple[Callable, str | Callable]] = {
        "context_builder": (
            lambda s: context_builder.context_builder(s, store),
            "rca_analyzer",
        ),
        "rca_analyzer": (
            rca_analyzer.rca_analyzer,
            "patch_generator",
        ),
        "patch_generator": (
            patch_generator.patch_generator,
            "human_approval",
        ),
        "human_approval": (
            human_approval.human_approval,
            _route_approval,
        ),
        "apply_patch": (
            lambda s: apply_patch.apply_patch(s, store),
            "retry_runner",
        ),
        "retry_runner": (
            lambda s: retry_runner.retry_runner(s, runner),
            _route_retry,
        ),
    }

    class _CompiledGraph:
        """Minimal LangGraph-compatible compiled graph."""

        def invoke(self, state: dict) -> dict:
            current_node = "context_builder"

            while current_node != END:
                node_fn, next_edge = nodes[current_node]

                # Run the node and merge partial updates into state
                updates = node_fn(state)
                if updates:
                    state.update(updates)

                # Resolve the next node
                if callable(next_edge):
                    current_node = next_edge(state)
                else:
                    current_node = next_edge

            return state

    return _CompiledGraph()
