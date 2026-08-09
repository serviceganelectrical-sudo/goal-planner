"""
Goal Planner — Streamlit web UI.
Uses the portable core in goal_engine.py.
"""

from __future__ import annotations

from datetime import date
from typing import Any

import streamlit as st

from goal_engine import GOAL_TYPES, analyze_goal, parse_goal_payload, plan_to_dict
from storage import delete_goal, ensure_dirs, get_goal, list_goals, save_goal
from streamlit_helpers import (
    as_date,
    goal_to_form_defaults,
    inject_styles,
    render_plan,
    safe_float,
)

st.set_page_config(
    page_title="Goal Planner",
    page_icon=":dart:",
    layout="wide",
    initial_sidebar_state="expanded",
)
inject_styles()


def main() -> None:
    ensure_dirs()

    if "form_defaults" not in st.session_state:
        st.session_state.form_defaults = goal_to_form_defaults(
            {
                "title": "",
                "goal_type": "financial",
                "unit": "USD",
                "start_value": 0,
                "target_value": 0,
                "timeframe_days": 90,
                "weekly_hours": 5,
                "weekly_budget": 100,
                "start_date": date.today().isoformat(),
            }
        )

    st.title("Goal Planner")
    st.markdown(
        '<p class="gp-muted">Define where you are, where you want to be, and what you can spend. '
        "Get a rate, a plan, and honest feasibility -- saved as local text files.</p>",
        unsafe_allow_html=True,
    )

    with st.sidebar:
        st.header("Saved plans")
        try:
            goals = list_goals()
        except Exception as exc:  # noqa: BLE001
            st.error(f"Could not load plans: {exc}")
            goals = []

        if not goals:
            st.caption("No saved plans yet.")
        else:
            for idx, g in enumerate(goals[:40]):
                gid = str(g.get("id") or f"idx{idx}")
                label = (g.get("title") or gid)[:48]
                status = "OK" if g.get("feasible") else "No" if g.get("feasible") is False else "|"
                cols = st.columns([3, 1])
                with cols[0]:
                    if st.button(f"{status} | {label}", key=f"open_{gid}_{idx}"):
                        try:
                            payload = get_goal(gid)
                            if not payload or not payload.get("goal"):
                                st.error("Could not open that plan.")
                            else:
                                st.session_state.form_defaults = goal_to_form_defaults(payload["goal"])
                                st.session_state.last_result = {
                                    "goal": payload.get("goal") or {},
                                    "plan": payload.get("plan") or {},
                                    "saved": {
                                        "id": payload.get("id"),
                                        "filename": payload.get("filename"),
                                    },
                                }
                                st.rerun()
                        except Exception as exc:  # noqa: BLE001
                            st.error(f"Open failed: {exc}")
                with cols[1]:
                    if st.button("Del", key=f"del_{gid}_{idx}"):
                        try:
                            delete_goal(gid)
                            if st.session_state.get("last_result", {}).get("saved", {}).get("id") == gid:
                                st.session_state.pop("last_result", None)
                            st.rerun()
                        except Exception as exc:  # noqa: BLE001
                            st.error(f"Delete failed: {exc}")

        st.divider()
        st.caption("Core: goal_engine.py | Storage: data/goals/")

    defaults = st.session_state.form_defaults
    type_labels = {k: v["label"] for k, v in GOAL_TYPES.items()}
    type_keys = list(type_labels.keys())
    goal_type_default = defaults.get("goal_type") if defaults.get("goal_type") in type_keys else "financial"
    type_index = type_keys.index(goal_type_default)

    with st.form("goal_form", clear_on_submit=False):
        st.subheader("Define your goal")
        title = st.text_input("Goal title", value=str(defaults.get("title") or ""))
        c1, c2 = st.columns(2)
        with c1:
            goal_type = st.selectbox(
                "Category",
                options=type_keys,
                format_func=lambda k: type_labels.get(k, k),
                index=type_index,
            )
        with c2:
            unit = st.text_input(
                "Unit of measure",
                value=str(defaults.get("unit") or GOAL_TYPES[goal_type_default]["default_unit"]),
            )

        st.markdown("**Starting state**")
        sc1, sc2 = st.columns(2)
        with sc1:
            start_value = st.number_input(
                "Numeric value (start)",
                value=float(defaults.get("start_value") or 0.0),
                step=1.0,
                format="%.4f",
            )
        with sc2:
            start_description = st.text_area(
                "Description (start)",
                value=str(defaults.get("start_description") or ""),
                height=80,
            )

        st.markdown("**Target outcome**")
        tc1, tc2 = st.columns(2)
        with tc1:
            target_value = st.number_input(
                "Numeric value (target)",
                value=float(defaults.get("target_value") or 0.0),
                step=1.0,
                format="%.4f",
            )
        with tc2:
            target_description = st.text_area(
                "Description (target)",
                value=str(defaults.get("target_description") or ""),
                height=80,
            )

        d1, d2 = st.columns(2)
        with d1:
            timeframe_days = st.number_input(
                "Timeframe (days)",
                min_value=1,
                max_value=3650,
                value=int(defaults.get("timeframe_days") or 90),
                step=1,
            )
        with d2:
            start_date = st.date_input(
                "Start date",
                value=as_date(defaults.get("start_date")),
                format="YYYY-MM-DD",
            )

        st.markdown("**Available resources**")
        r1, r2 = st.columns(2)
        with r1:
            weekly_hours = st.number_input(
                "Hours per week",
                min_value=0.0,
                value=float(defaults.get("weekly_hours") or 0.0),
                step=0.5,
            )
        with r2:
            weekly_budget = st.number_input(
                "Budget per week ($)",
                min_value=0.0,
                value=float(defaults.get("weekly_budget") or 0.0),
                step=1.0,
            )

        constraints = st.text_input("Constraints (optional)", value=str(defaults.get("constraints") or ""))
        notes = st.text_area("Notes (optional)", value=str(defaults.get("notes") or ""), height=70)
        save = st.checkbox("Save plan as a local text file", value=True)
        submitted = st.form_submit_button("Build plan", type="primary")

    if submitted:
        try:
            if isinstance(start_date, (tuple, list)):
                start_date_val = as_date(start_date[0] if start_date else date.today())
            else:
                start_date_val = as_date(start_date)

            data = {
                "title": (title or "").strip(),
                "goal_type": goal_type,
                "unit": (unit or "").strip() or GOAL_TYPES.get(goal_type, {}).get("default_unit", "units"),
                "start_value": start_value,
                "start_description": (start_description or "").strip(),
                "target_value": target_value,
                "target_description": (target_description or "").strip(),
                "timeframe_days": int(timeframe_days),
                "start_date": start_date_val.isoformat(),
                "weekly_hours": weekly_hours,
                "weekly_budget": weekly_budget,
                "constraints": (constraints or "").strip(),
                "notes": (notes or "").strip(),
            }

            st.session_state.form_defaults = goal_to_form_defaults(data)

            goal = parse_goal_payload(data)
            errors = goal.validate()
            if errors:
                st.error("; ".join(errors))
            else:
                plan = analyze_goal(goal)
                plan_dict = plan_to_dict(plan)
                goal_dict = {
                    "title": goal.title,
                    "goal_type": goal.goal_type,
                    "start_value": goal.start_value,
                    "start_description": goal.start_description,
                    "target_value": goal.target_value,
                    "target_description": goal.target_description,
                    "unit": goal.unit,
                    "timeframe_days": goal.timeframe_days,
                    "start_date": goal.start_date,
                    "weekly_hours": goal.weekly_hours,
                    "weekly_budget": goal.weekly_budget,
                    "constraints": goal.constraints,
                    "notes": goal.notes,
                }
                saved_meta = None
                if save:
                    saved_meta = save_goal(goal, plan)
                st.session_state.last_result = {
                    "goal": goal_dict,
                    "plan": plan_dict,
                    "saved": saved_meta,
                }
                st.success("Plan built.")
        except Exception as exc:  # noqa: BLE001
            st.error(f"Could not build plan: {exc}")

    if st.session_state.get("last_result"):
        res = st.session_state["last_result"]
        st.divider()
        try:
            render_plan(res.get("goal") or {}, res.get("plan") or {}, res.get("saved"))
        except Exception as exc:  # noqa: BLE001
            st.error(f"Could not display plan: {exc}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001
        st.error(f"App error: {exc}")
