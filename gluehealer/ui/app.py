"""
GlueHealer Web Application.

A modern, interactive Streamlit dashboard for showcasing the self-healing
agentic AI system. Supports both zero-setup production simulation mode
(for interviews and portfolio demonstrations) and live LLM execution mode.
"""
from __future__ import annotations

import os
import sys
import time
import streamlit as st

from gluehealer.ui.scenarios import SCENARIOS

# Page configuration
st.set_page_config(
    page_title="GlueHealer | Self-Healing Agent for AWS Glue",
    page_icon="🩹",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS for polished enterprise look
st.markdown(
    """
    <style>
    .main-header {
        font-size: 2.2rem;
        font-weight: 700;
        color: #1E293B;
        margin-bottom: 0.2rem;
    }
    .sub-header {
        font-size: 1.05rem;
        color: #64748B;
        margin-bottom: 1.5rem;
    }
    .badge-pill {
        display: inline-block;
        padding: 0.25rem 0.65rem;
        font-size: 0.78rem;
        font-weight: 600;
        border-radius: 9999px;
        margin-right: 0.4rem;
        background-color: #EEF2F6;
        color: #334155;
        border: 1px solid #CBD5E1;
    }
    .badge-aws {
        background-color: #FFF7ED;
        color: #C2410C;
        border: 1px solid #FDBA74;
    }
    .badge-safe {
        background-color: #ECFDF5;
        color: #047857;
        border: 1px solid #A7F3D0;
    }
    .badge-agent {
        background-color: #EFF6FF;
        color: #1D4ED8;
        border: 1px solid #BFDBFE;
    }
    .step-box {
        padding: 1rem;
        border-radius: 0.5rem;
        border: 1px solid #E2E8F0;
        background-color: #F8FAFC;
        margin-bottom: 1rem;
    }
    .status-card {
        padding: 0.8rem 1.2rem;
        border-radius: 0.5rem;
        margin-bottom: 1rem;
        font-weight: 600;
    }
    .status-failed {
        background-color: #FEF2F2;
        border: 1px solid #FCA5A5;
        color: #991B1B;
    }
    .status-healed {
        background-color: #ECFDF5;
        border: 1px solid #6EE7B7;
        color: #065F46;
    }
    .status-review {
        background-color: #EFF6FF;
        border: 1px solid #93C5FD;
        color: #1E40AF;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def init_session():
    """Initialize session state defaults."""
    if "mode" not in st.session_state:
        st.session_state.mode = "Showcase / Simulation Mode (Zero Setup)"
    if "scenario_id" not in st.session_state:
        st.session_state.scenario_id = "sales_schema_drift"
    if "current_step" not in st.session_state:
        st.session_state.current_step = 0  # 0: Failed, 1: Analyzed, 2: Diff Ready, 3: Approved/Applied, 4: Healed
    if "attempt" not in st.session_state:
        st.session_state.attempt = 1
    if "feedback_history" not in st.session_state:
        st.session_state.feedback_history = []
    if "is_revision" not in st.session_state:
        st.session_state.is_revision = False


init_session()

# --- Sidebar Configuration ---
with st.sidebar:
    st.image(
        "https://raw.githubusercontent.com/s3arajgupta/App-GlueHealer/main/GlueHealer%20workflow.png"
        if False else "https://img.icons8.com/fluency/96/healing.png",
        width=64,
    )
    st.title("🩹 GlueHealer")
    st.caption("Agentic Self-Healing for AWS Glue ETL Pipelines")

    st.divider()

    mode_options = [
        "Showcase / Simulation Mode (Zero Setup)",
        "Live Agent Engine (Local Scripts)",
    ]
    selected_mode = st.radio(
        "Execution Mode",
        options=mode_options,
        index=0 if st.session_state.mode == mode_options[0] else 1,
        help="Simulation Mode uses pre-recorded production scenarios ideal for interviews. Live Mode runs the actual agent graph on local files.",
    )
    if selected_mode != st.session_state.mode:
        st.session_state.mode = selected_mode
        st.session_state.current_step = 0
        st.session_state.attempt = 1
        st.session_state.feedback_history = []
        st.session_state.is_revision = False
        st.rerun()

    st.divider()

    if st.session_state.mode == "Showcase / Simulation Mode (Zero Setup)":
        st.subheader("Select Incident Scenario")
        scenario_labels = {k: v["title"] for k, v in SCENARIOS.items()}
        selected_scenario_id = st.selectbox(
            "Production Failure Incident",
            options=list(scenario_labels.keys()),
            format_func=lambda x: scenario_labels[x],
            index=list(scenario_labels.keys()).index(st.session_state.scenario_id),
        )
        if selected_scenario_id != st.session_state.scenario_id:
            st.session_state.scenario_id = selected_scenario_id
            st.session_state.current_step = 0
            st.session_state.attempt = 1
            st.session_state.feedback_history = []
            st.session_state.is_revision = False
            st.rerun()

        scenario = SCENARIOS[st.session_state.scenario_id]

        st.caption(f"**Glue Job:** `{scenario['job_name']}`")
        st.caption(f"**Job Run ID:** `{scenario['job_run_id']}`")
        st.caption(f"**Error Category:** `{scenario['error_type']}`")
        st.caption(f"**Compute Capacity:** `{scenario['dpu']} DPUs`")

    else:
        st.subheader("Live Script Runner")
        sample_scripts = {
            "sample_jobs/broken_etl.py": "Broken ETL (KeyError 'unit_price')",
            "sample_jobs/broken_transform.py": "Broken Transform (KeyError & ZeroDivisionError)",
        }
        selected_script = st.selectbox(
            "Choose Local Script to Heal",
            options=list(sample_scripts.keys()),
            format_func=lambda x: f"{x} - {sample_scripts[x]}",
        )
        auto_approve_live = st.checkbox("Auto-Approve Patches", value=False)

    st.divider()

    st.subheader("Safety Guardrails")
    st.markdown("✅ **Non-Destructive S3 Versioning** (`v1.py`, `v2.py`)")
    st.markdown("✅ **Human-in-the-Loop Review Gate**")
    st.markdown("✅ **Max Retry Cap:** 3 Attempts")
    st.markdown("✅ **Stateful Failure Loopback**")

    st.divider()

    if st.button("🔄 Reset Demo State", use_container_width=True):
        st.session_state.current_step = 0
        st.session_state.attempt = 1
        st.session_state.feedback_history = []
        st.session_state.is_revision = False
        st.rerun()


# --- Main Dashboard Header ---
st.markdown('<div class="main-header">🩹 GlueHealer Control Center</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="sub-header">LangGraph-Orchestrated Self-Healing System for AWS Glue ETL Pipelines</div>',
    unsafe_allow_html=True,
)

st.markdown(
    """
    <span class="badge-pill badge-aws">AWS Glue & S3</span>
    <span class="badge-pill badge-agent">LangGraph State Machine</span>
    <span class="badge-pill badge-safe">Zero-Overwrite Versioning</span>
    <span class="badge-pill badge-agent">Human-in-the-Loop Gate</span>
    """,
    unsafe_allow_html=True,
)
st.write("")

# ==============================================================================
# SIMULATION / SHOWCASE MODE
# ==============================================================================
if st.session_state.mode == "Showcase / Simulation Mode (Zero Setup)":
    scenario = SCENARIOS[st.session_state.scenario_id]

    # Status & Progress Overview
    col_stat1, col_stat2, col_stat3, col_stat4 = st.columns(4)

    with col_stat1:
        if st.session_state.current_step == 4:
            st.metric("Pipeline Status", "✅ HEALED", delta="Recovered")
        elif st.session_state.current_step == 2:
            st.metric("Pipeline Status", "⏸️ HUMAN REVIEW", delta="Awaiting Input")
        else:
            st.metric("Pipeline Status", "🚨 FAILED", delta="-Unresolved", delta_color="inverse")

    with col_stat2:
        st.metric("Healing Attempt", f"{st.session_state.attempt} of 3")

    with col_stat3:
        current_version = "v2.py" if st.session_state.is_revision else "v1.py"
        st.metric(
            "Target S3 Key",
            f"gluehealer-versions/{current_version}" if st.session_state.current_step >= 3 else "None (Pending)",
        )

    with col_stat4:
        nodes = ["Context Builder", "RCA Analyzer", "Human Approval", "Apply Patch", "Retry Runner"]
        active_node = nodes[min(st.session_state.current_step, len(nodes) - 1)]
        st.metric("Active Agent Node", active_node)

    st.write("")

    # Visual Workflow Stepper
    step_cols = st.columns(5)
    step_names = [
        "1. Ingest Failure",
        "2. RCA & Patch",
        "3. Human Review",
        "4. Apply Version",
        "5. Verify & Heal",
    ]
    for i, col in enumerate(step_cols):
        with col:
            if i < st.session_state.current_step:
                st.markdown(f"**{step_names[i]}**<br/>🟢 `Completed`", unsafe_allow_html=True)
            elif i == st.session_state.current_step:
                st.markdown(f"**{step_names[i]}**<br/>🔵 `Active`", unsafe_allow_html=True)
            else:
                st.markdown(f"**{step_names[i]}**<br/>⚪ `Pending`", unsafe_allow_html=True)

    st.divider()

    # --- Step 0: Job Failed & Ingested ---
    if st.session_state.current_step == 0:
        st.markdown(
            f'<div class="status-card status-failed">🚨 AWS Glue Job <code>{scenario["job_name"]}</code> failed in production. '
            f'Failure: <strong>{scenario["error_type"]}</strong></div>',
            unsafe_allow_html=True,
        )

        st.write(f"**Incident Summary:** {scenario['summary']}")

        col_left, col_right = st.columns(2)
        with col_left:
            st.subheader("📋 CloudWatch Error Logs (`/aws-glue/jobs/error`)")
            st.code(scenario["raw_error_logs"], language="text")

        with col_right:
            st.subheader(f"📄 Original ETL Script (`{scenario['s3_original_path']}`)")
            st.code(scenario["original_code"], language="python")

        st.write("")
        c1, c2 = st.columns([1, 4])
        with c1:
            if st.button("🚀 Trigger Agent Diagnosis", type="primary", use_container_width=True):
                with st.spinner("LangGraph Context Builder & RCA Analyzer running..."):
                    time.sleep(1.0)
                    st.session_state.current_step = 2  # move straight to review with RCA generated
                    st.rerun()

    # --- Step 2: Human Review Gate (RCA + Unified Diff + Approval) ---
    elif st.session_state.current_step in (1, 2):
        st.markdown(
            '<div class="status-card status-review">🔍 RCA & Proposed Patch Generated. '
            '<strong>Human Approval Gate Active</strong> — No changes are applied without explicit approval.</div>',
            unsafe_allow_html=True,
        )

        tab_rca, tab_diff, tab_code = st.tabs(["🔍 Root Cause Analysis", "🩹 Unified Diff Review", "📄 Complete Patched Code"])

        with tab_rca:
            st.markdown(scenario["rca_analysis"])
            if st.session_state.is_revision and st.session_state.feedback_history:
                st.info(f"💡 **Cyclic Revision History:** Previous attempt was rejected with feedback: *\"{st.session_state.feedback_history[-1]}\"*. The patch below was regenerated taking this critique into account.")

        with tab_diff:
            st.caption("Green lines indicate non-destructive additions. Red lines indicate removals.")
            diff_text = scenario["diff_v2_feedback"] if st.session_state.is_revision else scenario["diff_v1"]
            st.code(diff_text, language="diff")

        with tab_code:
            code_text = scenario["patched_code_v1"]
            st.code(code_text, language="python")

        st.divider()

        st.subheader("🛡️ Human Approval Gate")
        col_approve, col_reject = st.columns([1, 1])

        with col_approve:
            st.markdown("#### ✅ Approve Patch")
            target_v = "v2.py" if st.session_state.is_revision else "v1.py"
            st.write(f"Apply this patch non-destructively to `s3://.../gluehealer-versions/{target_v}` and re-trigger Glue job.")
            if st.button("Approve & Deploy Patch 🚀", type="primary", use_container_width=True):
                with st.spinner("Deploying versioned script to S3 and triggering Glue Job Run..."):
                    time.sleep(1.2)
                    st.session_state.current_step = 4
                    st.rerun()

        with col_reject:
            st.markdown("#### ❌ Reject with Feedback")
            st.write("Demonstrates the **cyclic state machine**: loops back to Context Builder with reviewer guidance.")
            default_feedback = "Use defensive get() and round to 2 decimals" if not st.session_state.is_revision else "Looks good"
            rejection_notes = st.text_input(
                "Feedback for LLM Agent",
                value=default_feedback,
                placeholder="e.g. Please use .get() instead of changing the column name",
            )
            if st.button("Reject & Request Revision 🔁", use_container_width=True):
                if rejection_notes.strip():
                    with st.spinner("Routing feedback back through Context Builder for revised patch..."):
                        time.sleep(1.2)
                        st.session_state.feedback_history.append(rejection_notes)
                        st.session_state.attempt += 1
                        st.session_state.is_revision = True
                        st.session_state.current_step = 2
                        st.rerun()
                else:
                    st.warning("Please provide a brief feedback note before rejecting.")

    # --- Step 4: Verification & Healed ---
    elif st.session_state.current_step == 4:
        st.markdown(
            f'<div class="status-card status-healed">🎉 AWS Glue Job <code>{scenario["job_name"]}</code> '
            f'<strong>SUCCESSFULLY HEALED</strong> in Attempt {st.session_state.attempt}!</div>',
            unsafe_allow_html=True,
        )

        st.balloons()

        col_h1, col_h2 = st.columns(2)
        with col_h1:
            st.subheader("📜 Retried Glue Job Run Logs")
            st.code(scenario["execution_log_healed"], language="text")

        with col_h2:
            st.subheader("🛡️ Production Safety Audit")
            v_num = "v2.py" if st.session_state.is_revision else "v1.py"
            st.success(f"**Versioned S3 Artifact:** Created `gluehealer-versions/{scenario['job_name']}/{v_num}`")
            st.info(f"**Original Script Status:** `{scenario['s3_original_path']}` (100% Unmodified / Zero In-Place Overwrites)")
            st.metric("Total Retries Needed", f"{st.session_state.attempt} / 3")

            if st.session_state.feedback_history:
                st.write("**Human Critiques Incorporated:**")
                for idx, fb in enumerate(st.session_state.feedback_history, 1):
                    st.write(f"- Cycle {idx}: *\"{fb}\"*")

            st.write("")
            if st.button("🔄 Test Another Incident Scenario", use_container_width=True):
                st.session_state.current_step = 0
                st.session_state.attempt = 1
                st.session_state.feedback_history = []
                st.session_state.is_revision = False
                st.rerun()


# ==============================================================================
# LIVE AGENT ENGINE (LOCAL SCRIPTS)
# ==============================================================================
else:
    st.subheader(f"⚡ Live Agent Engine: Healing `{selected_script}`")
    st.caption("Runs the real cyclic LangGraph executor with OpenRouter LLM on your local machine.")

    if not os.path.exists(selected_script):
        st.error(f"Script file `{selected_script}` not found on disk.")
    else:
        with open(selected_script, "r", encoding="utf-8") as f:
            script_code = f.read()

        col_code, col_run = st.columns([1, 1])

        with col_code:
            st.subheader("Current Script Source")
            st.code(script_code, language="python")

        with col_run:
            st.subheader("Live Healing Pipeline")
            st.write("Click below to test run the script, detect failure, execute RCA, generate patch, and retry.")

            if st.button("🚀 Execute Live Self-Healing Pipeline", type="primary", use_container_width=True):
                from gluehealer.tools.local import LocalJobRunner, LocalScriptStore
                from gluehealer.graph import build_graph

                # Step 1: Initial run
                st.write("🔍 Running script to capture runtime stderr...")
                runner = LocalJobRunner()
                success, stdout, stderr = runner.run_job(os.path.abspath(selected_script))

                if success:
                    st.success("✅ Job ran successfully — nothing to heal!")
                    if stdout:
                        st.code(stdout)
                else:
                    st.error("❌ Job failed as expected. Error output:")
                    st.code(stderr, language="text")

                    with st.spinner("🤖 Calling Agent Pipeline (Context Builder ➔ RCA ➔ Patch Generator)..."):
                        graph = build_graph()
                        job_name = os.path.splitext(os.path.basename(selected_script))[0]
                        initial_state = {
                            "job_name": job_name,
                            "script_path": os.path.abspath(selected_script),
                            "original_script_path": os.path.abspath(selected_script),
                            "script_content": "",
                            "error_logs": stderr,
                            "historical_patches": [],
                            "rca_result": "",
                            "corrected_script": "",
                            "patch_display": "",
                            "human_feedback": "",
                            "patched_script_path": "",
                            "retry_count": 0,
                            "max_retries": 3,
                            "auto_approve": auto_approve_live,
                            "status": "failed",
                            "run_output": "",
                        }

                        # Invoke
                        final_state = graph.invoke(initial_state)

                    if final_state["status"] == "healed":
                        st.success(f"🎉 Job '{job_name}' successfully healed in {final_state['retry_count']} attempt(s)!")
                        st.markdown(f"**Healed script created at:** `{final_state['patched_script_path']}`")
                        st.markdown("### Generated Diff:")
                        st.code(final_state["patch_display"], language="diff")
                        st.markdown("### Retried Run Output:")
                        st.code(final_state["run_output"], language="text")
                    else:
                        st.warning(f"Pipeline finished with status: {final_state['status']}")
                        if final_state.get("patch_display"):
                            st.code(final_state["patch_display"], language="diff")


# Footer
st.divider()
st.markdown(
    """
    <div style="text-align: center; color: #94A3B8; font-size: 0.85rem;">
        GlueHealer — Autonomous Self-Healing Agent for AWS Glue Pipelines • MIT License
    </div>
    """,
    unsafe_allow_html=True,
)
