"""Helpers for Streamlit Goal Planner UI."""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

import streamlit as st

from goal_engine import GOAL_TYPES, analyze_goal, parse_goal_payload, plan_to_dict
from storage import delete_goal, ensure_dirs, get_goal, list_goals, save_goal


def inject_styles() -> None:
    st.markdown(
        """
    <style>
      .stApp { background: #0a0a0b; color: #f4f4f5; }
      [data-testid="stSidebar"] {
        background: #121214;
        border-right: 1px solid rgba(244,244,245,0.12);
      }
      [data-testid="stMetric"] {
        background: #1a1a1e;
        border: 1px solid rgba(244,244,245,0.12);
        border-radius: 12px;
        padding: 12px 16px;
      }
      div[data-testid="stForm"] {
        background: #121214;
        border: 1px solid rgba(244,244,245,0.12);
        border-radius: 16px;
        padding: 1.25rem 1.5rem 1.5rem;
      }
      .block-container { padding-top: 1.5rem; max-width: 1100px; }
      .gp-badge-ok {
        display: inline-block; padding: 0.3rem 0.75rem; border-radius: 999px;
        background: rgba(110,231,183,0.12); color: #6ee7b7; font-size: 0.75rem;
        font-weight: 600; letter-spacing: 0.04em; text-transform: uppercase;
      }
      .gp-badge-bad {
        display: inline-block; padding: 0.3rem 0.75rem; border-radius: 999px;
        background: rgba(248,113,113,0.12); color: #f87171; font-size: 0.75rem;
        font-weight: 600; letter-spacing: 0.04em; text-transform: uppercase;
      }
      .gp-muted { color: #a1a1aa; font-size: 0.95rem; }
    </style>
    """,
        unsafe_allow_html=True,
    )


def as_date(value: Any) -> date:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str) and value.strip():
        try:
            return date.fromisoformat(value.strip()[:10])
        except ValueError:
            pass
    return date.today()


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def render_plan(goal: dict, plan: dict, saved: dict | None = None) -> None:
    feasible = bool(plan.get("feasible"))
    metrics = plan.get("metrics") or {}
    unit = str(metrics.get("unit") or goal.get("unit") or "")

    badge = (
        '<span class="gp-badge-ok">Feasible</span>'
        if feasible
        else '<span class="gp-badge-bad">Not feasible</span>'
    )
    st.markdown(badge, unsafe_allow_html=True)
    st.markdown(f"### {goal.get('title') or 'Plan'}")
    st.write(plan.get("summary") or "")

    if saved and saved.get("filename"):
        st.caption(f"Saved as `{saved.get('filename')}` under data/goals/")

    gap = safe_float(metrics.get("absolute_gap"))
    weekly = abs(safe_float(metrics.get("weekly_rate_required")))
    daily = abs(safe_float(metrics.get("daily_rate_required")))
    cap = max(0.0, safe_float(metrics.get("capacity_pct")))

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Gap", f"{gap:g} {unit}".strip())
    c2.metric("Weekly rate", f"{weekly:.2f} {unit}".strip())
    c3.metric("Daily rate", f"{daily:.2f} {unit}".strip())
    c4.metric("Capacity", f"{cap:.0f}%")

    st.progress(min(1.0, max(0.0, cap / 100.0)))

    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("**Starting state**")
        st.write(f"{goal.get('start_value')} {unit}".strip())
        if goal.get("start_description"):
            st.caption(str(goal["start_description"]))
    with col_b:
        st.markdown("**Target outcome**")
        st.write(f"{goal.get('target_value')} {unit}".strip())
        if goal.get("target_description"):
            st.caption(str(goal["target_description"]))

    with st.expander("Gap analysis", expanded=True):
        for line in plan.get("gap_analysis") or []:
            st.markdown(f"- {line}")

    warnings = plan.get("warnings") or []
    if warnings:
        with st.expander("Warnings", expanded=True):
            for w in warnings:
                st.warning(str(w))

    st.subheader("Step-by-step plan")
    for step in plan.get("steps") or []:
        order = step.get("order", "")
        title = step.get("title") or ""
        detail = step.get("detail") or ""
        st.markdown(f"**{order}. {title}**")
        st.caption(detail)

    st.subheader("Milestones")
    for m in plan.get("milestones") or []:
        st.markdown(
            f"**Week {m.get('week')}** · {m.get('date_label')} · "
            f"target {m.get('target_value')} {unit}".strip()
        )
        if m.get("focus"):
            st.caption(str(m.get("focus")))
        for a in m.get("actions") or []:
            st.markdown(f"- {a}")

    st.subheader("Suggested adjustments" if not feasible else "Sustain & fine-tune")
    for adj in plan.get("adjustments") or []:
        st.markdown(f"**{adj.get('category') or 'Note'}** — {adj.get('suggestion') or ''}")
        if adj.get("impact"):
            st.caption(str(adj.get("impact")))


def goal_to_form_defaults(g: dict) -> dict:
    return {
        "title": str(g.get("title") or ""),
        "goal_type": str(g.get("goal_type") or "financial"),
        "unit": str(g.get("unit") or "USD"),
        "start_value": safe_float(g.get("start_value")),
        "start_description": str(g.get("start_description") or ""),
        "target_value": safe_float(g.get("target_value")),
        "target_description": str(g.get("target_description") or ""),
        "timeframe_days": max(1, int(safe_float(g.get("timeframe_days"), 90))),
        "start_date": as_date(g.get("start_date")),
        "weekly_hours": max(0.0, safe_float(g.get("weekly_hours"), 5)),
        "weekly_budget": max(0.0, safe_float(g.get("weekly_budget"), 100)),
        "constraints": str(g.get("constraints") or ""),
        "notes": str(g.get("notes") or ""),
    }
