"""Goal Planner data models and parsing."""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any

GOAL_TYPES = {
    "financial": {
        "label": "Financial",
        "default_unit": "USD",
        "rate_label": "per week",
        "resource_hint": "weekly savings capacity, side income, budget cuts",
    },
    "fitness": {
        "label": "Fitness / Health",
        "default_unit": "units",
        "rate_label": "per week",
        "resource_hint": "training hours, equipment, recovery days",
    },
    "learning": {
        "label": "Learning / Skill",
        "default_unit": "hours",
        "rate_label": "hours per week",
        "resource_hint": "study hours, courses, mentorship",
    },
    "career": {
        "label": "Career / Work",
        "default_unit": "units",
        "rate_label": "per week",
        "resource_hint": "weekly hours, network, budget for tools",
    },
    "creative": {
        "label": "Creative Project",
        "default_unit": "units",
        "rate_label": "per week",
        "resource_hint": "creative hours, materials budget",
    },
    "custom": {
        "label": "Custom",
        "default_unit": "units",
        "rate_label": "per week",
        "resource_hint": "available time and budget",
    },
}


@dataclass
class GoalInput:
    title: str
    goal_type: str
    start_value: float
    target_value: float
    unit: str
    timeframe_days: int
    weekly_hours: float
    weekly_budget: float
    start_description: str = ""
    target_description: str = ""
    notes: str = ""
    constraints: str = ""
    start_date: str = ""

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not self.title or not self.title.strip():
            errors.append("Title is required.")
        if self.goal_type not in GOAL_TYPES:
            errors.append("Unknown goal type.")
        if self.timeframe_days < 1:
            errors.append("Timeframe must be at least 1 day.")
        if self.timeframe_days > 3650:
            errors.append("Timeframe cannot exceed 10 years.")
        if self.weekly_hours < 0:
            errors.append("Weekly hours cannot be negative.")
        if self.weekly_budget < 0:
            errors.append("Weekly budget cannot be negative.")
        if math.isnan(self.start_value) or math.isnan(self.target_value):
            errors.append("Start and target must be numbers.")
        if self.start_value == self.target_value:
            errors.append("Start and target are the same — there is no gap to close.")
        return errors


@dataclass
class Milestone:
    week: int
    date_label: str
    target_value: float
    focus: str
    actions: list[str] = field(default_factory=list)


@dataclass
class Adjustment:
    category: str
    suggestion: str
    impact: str


@dataclass
class PlanResult:
    feasible: bool
    gap: float
    direction: str  # "increase" | "decrease"
    absolute_gap: float
    weekly_rate_required: float
    daily_rate_required: float
    capacity_score: float
    capacity_note: str
    summary: str
    gap_analysis: list[str]
    milestones: list[Milestone]
    steps: list[dict[str, Any]]
    adjustments: list[Adjustment]
    warnings: list[str]
    metrics: dict[str, Any]


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def parse_goal_payload(data: dict[str, Any]) -> GoalInput:
    goal_type = str(data.get("goal_type") or "custom").strip().lower()
    if goal_type not in GOAL_TYPES:
        goal_type = "custom"

    unit = str(data.get("unit") or GOAL_TYPES[goal_type]["default_unit"]).strip()
    start_date = str(data.get("start_date") or date.today().isoformat()).strip()

    return GoalInput(
        title=str(data.get("title") or "").strip(),
        goal_type=goal_type,
        start_value=_safe_float(data.get("start_value")),
        target_value=_safe_float(data.get("target_value")),
        unit=unit or GOAL_TYPES[goal_type]["default_unit"],
        timeframe_days=max(1, int(_safe_float(data.get("timeframe_days"), 30))),
        weekly_hours=_safe_float(data.get("weekly_hours")),
        weekly_budget=_safe_float(data.get("weekly_budget")),
        start_description=str(data.get("start_description") or "").strip(),
        target_description=str(data.get("target_description") or "").strip(),
        notes=str(data.get("notes") or "").strip(),
        constraints=str(data.get("constraints") or "").strip(),
        start_date=start_date,
    )
