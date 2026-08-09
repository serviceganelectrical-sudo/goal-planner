"""Goal analysis engine: gap identification, progress rates, plans, and feasibility.

Public API re-exported for portable use across Streamlit, CLI, and HTTP.
"""
from __future__ import annotations

from ge_models import (
    GOAL_TYPES,
    Adjustment,
    GoalInput,
    Milestone,
    PlanResult,
    parse_goal_payload,
)
from ge_plan import analyze_goal, plan_to_dict, slugify

__all__ = [
    "GOAL_TYPES",
    "GoalInput",
    "Milestone",
    "Adjustment",
    "PlanResult",
    "parse_goal_payload",
    "analyze_goal",
    "plan_to_dict",
    "slugify",
]
