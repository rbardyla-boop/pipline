"""Research UI — Streamlit entry point.

4MAT-aligned layout:
  Tab 1 (Q1 WHY)  — Hypothesis Composer
  Tab 2 (Q2 WHAT) — Live Dynamics
  Tab 3 (Q3 HOW)  — Variant Controls
  Tab 4 (Q4 IF)   — Discovery Journal

Run with:
  streamlit run frontend/app.py --server.port 8501
"""

from __future__ import annotations

import sys
import os
import time

# Ensure project root is on path regardless of cwd
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

from frontend.state import BackgroundRunner, LoopEvent, LoopState
from frontend.components import (
    discovery_journal,
    hypothesis_composer,
    live_dynamics,
    variant_controls,
)


# ------------------------------------------------------------------ #
# Page config                                                         #
# ------------------------------------------------------------------ #

st.set_page_config(
    page_title="UAF Research Workbench",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="collapsed",
)

_CSS = """
<style>
    .stApp { background-color: #0F0F1A; }
    h1, h2, h3, h4 { color: #E2E8F0; }
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        background: #1A1A2E;
        padding: 8px 12px;
        border-radius: 8px;
    }
    .stTabs [data-baseweb="tab"] {
        background: transparent;
        color: #94A3B8;
        border-radius: 6px;
        font-size: 0.9rem;
        padding: 6px 16px;
    }
    .stTabs [aria-selected="true"] {
        background: #7C3AED !important;
        color: white !important;
    }
    [data-testid="stMetricValue"] { color: #7C3AED; font-size: 1.4rem; }
    [data-testid="stMetricLabel"] { color: #94A3B8; }
    .stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #7C3AED, #4F46E5);
        border: none;
        color: white;
    }
    .stButton > button[kind="primary"]:hover { opacity: 0.9; }
</style>
"""
st.markdown(_CSS, unsafe_allow_html=True)


# ------------------------------------------------------------------ #
# Session state initialisation                                        #
# ------------------------------------------------------------------ #

if "loop_state" not in st.session_state:
    st.session_state.loop_state = LoopState()

if "runner" not in st.session_state:
    st.session_state.runner = BackgroundRunner()

if "auto_refresh" not in st.session_state:
    st.session_state.auto_refresh = False


def _state() -> LoopState:
    return st.session_state.loop_state


def _runner() -> BackgroundRunner:
    return st.session_state.runner


# ------------------------------------------------------------------ #
# Drain background events into session state                          #
# ------------------------------------------------------------------ #

def _drain_events() -> None:
    runner = _runner()
    state = _state()
    new_events = runner.drain_events()
    for event in new_events:
        if event.kind == "iteration":
            state.iteration_results.append(event.payload)
            state.status = "running"
        elif event.kind == "complete":
            state.status = "complete"
            state.resolution = str(event.payload)
            st.session_state.auto_refresh = False
        elif event.kind == "error":
            state.status = "error"
            state.error_message = str(event.payload)
            st.session_state.auto_refresh = False

    if runner.is_alive() and state.status == "running":
        st.session_state.auto_refresh = True
    elif state.status in ("complete", "error"):
        st.session_state.auto_refresh = False
    else:
        st.session_state.auto_refresh = runner.is_alive()


# ------------------------------------------------------------------ #
# Header                                                              #
# ------------------------------------------------------------------ #

st.markdown(
    "<h1 style='margin-bottom:0'>🔬 UAF Research Workbench</h1>"
    "<p style='color:#94A3B8;margin-top:4px'>Hypothesis-driven AI architecture discovery</p>",
    unsafe_allow_html=True,
)

# Global control strip
ctrl_cols = st.columns([1, 1, 1, 1, 4])

with ctrl_cols[0]:
    if st.button("⏸ Pause", disabled=_state().status != "running"):
        _runner().pause()
        _state().status = "paused"

with ctrl_cols[1]:
    if st.button("▶ Resume", disabled=_state().status != "paused"):
        _runner().resume()
        _state().status = "running"

with ctrl_cols[2]:
    if st.button("⏹ Stop", disabled=_state().status not in ("running", "paused")):
        _runner().stop()
        _state().status = "idle"
        st.session_state.auto_refresh = False

with ctrl_cols[3]:
    if st.button("↺ Reset"):
        _runner().stop()
        st.session_state.loop_state = LoopState()
        st.session_state.runner = BackgroundRunner()
        st.session_state.auto_refresh = False
        st.rerun()

with ctrl_cols[4]:
    status = _state().status
    color_map = {
        "idle": "#94A3B8",
        "running": "#10B981",
        "paused": "#F59E0B",
        "complete": "#7C3AED",
        "error": "#EF4444",
    }
    color = color_map.get(status, "#94A3B8")
    st.markdown(
        f"<span style='color:{color};font-weight:600;font-size:1rem'>"
        f"● {status.upper()}</span>",
        unsafe_allow_html=True,
    )
    if _state().error_message:
        st.error(_state().error_message)

st.markdown("---")

# ------------------------------------------------------------------ #
# Drain events before rendering tabs                                  #
# ------------------------------------------------------------------ #

_drain_events()

# ------------------------------------------------------------------ #
# 4MAT tabs                                                           #
# ------------------------------------------------------------------ #

tab_q1, tab_q2, tab_q3, tab_q4 = st.tabs([
    "Q1 — WHY  (Hypothesis)",
    "Q2 — WHAT (Live Dynamics)",
    "Q3 — HOW  (Variant Controls)",
    "Q4 — IF   (Discovery Journal)",
])

with tab_q1:
    hypothesis = hypothesis_composer.render()
    if hypothesis is not None and _state().status in ("idle", "complete", "error"):
        # User clicked Run — start background runner
        _state().hypothesis = hypothesis
        _state().iteration_results = []
        _state().status = "running"
        _state().resolution = ""
        _state().error_message = ""

        max_iter = 4
        record_ledger = True

        _runner().start(
            hypothesis=hypothesis,
            max_iterations=max_iter,
            record_to_ledger=record_ledger,
        )
        st.session_state.auto_refresh = True
        st.rerun()

with tab_q2:
    live_dynamics.render(_state())

with tab_q3:
    latest = _state().latest_summaries()
    variant_controls.render(
        summaries=latest,
        inject_fn=_runner().inject_variant,
    )

with tab_q4:
    discovery_journal.render(_state(), _runner())

# ------------------------------------------------------------------ #
# Auto-refresh while running                                          #
# ------------------------------------------------------------------ #

if st.session_state.auto_refresh and _runner().is_alive():
    time.sleep(2)
    st.rerun()
