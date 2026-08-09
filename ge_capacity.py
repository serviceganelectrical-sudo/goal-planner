"""Capacity estimation and milestone building."""
from __future__ import annotations

import math
from datetime import date, datetime, timedelta
from typing import Any

from ge_models import GOAL_TYPES, GoalInput, Milestone, _safe_float


def _weeks_in_timeframe(days: int) -> float:
    return max(days / 7.0, 1 / 7.0)


def _estimate_capacity(goal: GoalInput, weekly_rate_needed: float) -> tuple[float, str]:
    """
    Estimate how much of the required weekly rate the user can sustain.
    Returns capacity_score (0–1+) and a human note.
    Capacity uses hours and budget as proxy resources relative to goal type.
    """
    gt = goal.goal_type
    hours = goal.weekly_hours
    budget = goal.weekly_budget
    unit = goal.unit.lower()
    needed = abs(weekly_rate_needed)

    if needed == 0:
        return 1.0, "No progress required."

    # Type-aware productivity assumptions (units of progress per resource unit)
    if gt == "financial" or unit in {"usd", "$", "eur", "gbp", "dollars", "money"}:
        # Weekly budget is direct contribution; hours can convert via earning (~$20/hr default)
        earning_rate = 20.0
        if "hour" in unit:
            earning_rate = 1.0
        capacity_units = budget + (hours * earning_rate * 0.35)
        note = (
            f"Estimated weekly capacity ≈ {capacity_units:,.0f} {goal.unit} "
            f"from budget ({budget:,.0f}) plus part of available hours as earning power."
        )
    elif gt == "learning":
        # Learning progress is mostly hours; budget buys courses but not auto-hours
        effective_hours = hours * 0.75  # focus efficiency
        if "hour" in unit or unit in {"hrs", "h"}:
            capacity_units = effective_hours
        else:
            capacity_units = effective_hours * 1.0  # 1 unit per focused hour
        note = (
            f"Estimated weekly learning capacity ≈ {capacity_units:,.1f} {goal.unit} "
            f"from {hours:g} available hours (75% focus efficiency)."
        )
    elif gt == "fitness":
        # Diminishing returns; 3–6 quality sessions/week is sustainable
        session_value = max(hours / 3.0, 0.1)  # rough progress units per week
        capacity_units = min(hours * 0.4, session_value * 4)
        if hours <= 0:
            capacity_units = 0
        note = (
            f"Estimated weekly fitness capacity ≈ {capacity_units:,.2f} {goal.unit} "
            f"from {hours:g} training hours (recovery-aware)."
        )
    else:
        # Generic: hours are primary, budget is secondary boost
        capacity_units = hours * 0.5 + budget * 0.05
        note = (
            f"Estimated weekly capacity ≈ {capacity_units:,.2f} {goal.unit} "
            f"from time ({hours:g} h) and budget (${budget:,.0f})."
        )

    if capacity_units <= 0:
        return 0.0, "No usable capacity detected from the resources you listed."

    score = capacity_units / needed
    return score, note


def _milestone_focus(goal: GoalInput, phase: int, total_phases: int) -> str:
    ratio = phase / max(total_phases, 1)
    gt = goal.goal_type
    if ratio <= 0.25:
        base = "Foundation — systems, baseline measurement, and friction removal"
    elif ratio <= 0.5:
        base = "Momentum — consistent cadence and measurable weekly output"
    elif ratio <= 0.75:
        base = "Acceleration — optimize, remove bottlenecks, raise quality"
    else:
        base = "Close-out — protect gains, finish strong, plan maintenance"

    type_notes = {
        "financial": "Track every transfer; automate savings first.",
        "fitness": "Prioritize recovery and progressive overload.",
        "learning": "Active recall and projects over passive watching.",
        "career": "Ship visible work and seek feedback weekly.",
        "creative": "Ship drafts early; revise in later phases.",
        "custom": "Protect focus blocks; review numbers weekly.",
    }
    return f"{base} {type_notes.get(gt, type_notes['custom'])}"


def _phase_actions(goal: GoalInput, phase: int, weekly_rate: float) -> list[str]:
    unit = goal.unit
    rate = abs(weekly_rate)
    actions = [
        f"Hit this week's target of {rate:,.2f} {unit} of progress.",
        "Log results every Sunday and adjust the next week if behind by >10%.",
    ]
    if goal.weekly_hours > 0:
        actions.append(
            f"Block {goal.weekly_hours:g} focused hours on your calendar in advance."
        )
    if goal.weekly_budget > 0 and goal.goal_type == "financial":
        actions.append(
            f"Move ${goal.weekly_budget:,.2f} into the goal account on payday."
        )
    elif goal.weekly_budget > 0:
        actions.append(
            f"Allocate up to ${goal.weekly_budget:,.2f} this week only if it multiplies progress."
        )

    if phase == 1:
        actions.insert(0, "Define your weekly review ritual and write the success metric.")
        if goal.start_description:
            actions.insert(
                1,
                f"Document baseline in your own words: {goal.start_description[:140]}",
            )
    if phase >= max(1, 1) and goal.target_description and phase == 1:
        actions.append(
            f"Keep the finish-line picture visible: {goal.target_description[:140]}"
        )
    if goal.constraints:
        actions.append(f"Respect constraint: {goal.constraints[:120]}")
    return actions[:6]


def _build_milestones(goal: GoalInput, weekly_rate: float) -> list[Milestone]:
    weeks = max(1, math.ceil(goal.timeframe_days / 7))
    # Cap milestone count for readability
    if weeks <= 8:
        step = 1
    elif weeks <= 24:
        step = 2
    else:
        step = max(1, weeks // 8)

    try:
        start = datetime.strptime(goal.start_date, "%Y-%m-%d").date()
    except ValueError:
        start = date.today()

    milestones: list[Milestone] = []
    total_phases = max(1, math.ceil(weeks / step))
    phase = 0
    for w in range(step, weeks + 1, step):
        phase += 1
        progress = weekly_rate * w
        value = goal.start_value + progress
        # Clamp to target on final milestone
        if w >= weeks:
            value = goal.target_value
            w = weeks
        day = start + timedelta(days=min(goal.timeframe_days, w * 7))
        milestones.append(
            Milestone(
                week=w,
                date_label=day.isoformat(),
                target_value=round(value, 2),
                focus=_milestone_focus(goal, phase, total_phases),
                actions=_phase_actions(goal, phase, weekly_rate),
            )
        )
        if w >= weeks:
            break

    # Ensure final milestone lands on target if loop skipped end
    if not milestones or milestones[-1].target_value != round(goal.target_value, 2):
        end = start + timedelta(days=goal.timeframe_days)
        milestones.append(
            Milestone(
                week=weeks,
                date_label=end.isoformat(),
                target_value=round(goal.target_value, 2),
                focus=_milestone_focus(goal, total_phases, total_phases),
                actions=_phase_actions(goal, total_phases, weekly_rate),
            )
        )
    return milestones
