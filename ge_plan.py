"""Plan construction: steps, adjustments, analyze_goal."""
from __future__ import annotations

import math
import re
from datetime import date, datetime, timedelta
from typing import Any

from ge_models import (
    GOAL_TYPES,
    Adjustment,
    GoalInput,
    Milestone,
    PlanResult,
    _safe_float,
    parse_goal_payload,
)
from ge_capacity import (
    _build_milestones,
    _estimate_capacity,
    _milestone_focus,
    _phase_actions,
    _weeks_in_timeframe,
)


def _build_steps(goal: GoalInput, weekly_rate: float, feasible: bool) -> list[dict[str, Any]]:
    direction = "increase" if goal.target_value > goal.start_value else "decrease"
    abs_rate = abs(weekly_rate)

    done_line = (
        f"reach {goal.target_value:g} {goal.unit} from {goal.start_value:g} {goal.unit} "
        f"within {goal.timeframe_days} days"
    )
    if goal.target_description:
        done_line += f" — “{goal.target_description}”"

    baseline_detail = (
        f"Choose a single tracking method for {goal.unit} (spreadsheet, app, or "
        f"notebook). Log the starting value ({goal.start_value:g}) today."
    )
    if goal.start_description:
        baseline_detail += f" Baseline in your words: “{goal.start_description}”."

    steps: list[dict[str, Any]] = [
        {
            "order": 1,
            "title": "Clarify the finish line",
            "detail": f"Write a one-sentence definition of done: {done_line}.",
        },
        {
            "order": 2,
            "title": "Instrument measurement",
            "detail": baseline_detail,
        },
        {
            "order": 3,
            "title": "Set the weekly cadence",
            "detail": (
                f"Required rate is {abs_rate:,.2f} {goal.unit} per week "
                f"({direction}). Schedule your {goal.weekly_hours:g} hours and protect them."
            ),
        },
        {
            "order": 4,
            "title": "Run a 2-week pilot",
            "detail": (
                "For the first 14 days, execute the weekly rate and note friction. "
                "Adjust tools and environment before scaling intensity."
            ),
        },
        {
            "order": 5,
            "title": "Install a weekly review",
            "detail": (
                "Every week: compare actual vs required rate, list one bottleneck, "
                "and set the next week's three actions."
            ),
        },
        {
            "order": 6,
            "title": "Hit mid-point checkpoint",
            "detail": (
                f"At day {goal.timeframe_days // 2}, you should be near "
                f"{goal.start_value + (goal.target_value - goal.start_value) / 2:,.2f} "
                f"{goal.unit}. If off by >15%, revise resources or deadline."
            ),
        },
        {
            "order": 7,
            "title": "Final push and maintenance",
            "detail": (
                "In the last 20% of the timeframe, prioritize the highest-leverage actions "
                "and define how you will maintain the outcome after target day."
                + (
                    f" Success looks like: “{goal.target_description}”."
                    if goal.target_description
                    else ""
                )
            ),
        },
    ]

    if not feasible:
        steps.insert(
            3,
            {
                "order": 3,
                "title": "Resolve the feasibility gap first",
                "detail": (
                    "Before full execution, apply the suggested adjustments to time, budget, "
                    "or deadline so the required rate becomes sustainable."
                ),
            },
        )
        # re-number
        for i, s in enumerate(steps, start=1):
            s["order"] = i

    return steps


def _suggest_adjustments(
    goal: GoalInput,
    weekly_rate: float,
    capacity_score: float,
) -> list[Adjustment]:
    if capacity_score >= 1.0:
        return [
            Adjustment(
                category="Sustain",
                suggestion="Resources look sufficient. Keep a 10–15% buffer for setbacks.",
                impact="Improves reliability without changing the deadline.",
            )
        ]

    needed = abs(weekly_rate)
    shortfall = max(0.0, 1.0 - capacity_score)
    adjustments: list[Adjustment] = []

    # Extend timeframe
    if capacity_score > 0:
        new_weeks = math.ceil((_weeks_in_timeframe(goal.timeframe_days) / capacity_score))
        new_days = int(new_weeks * 7)
        adjustments.append(
            Adjustment(
                category="Timeframe",
                suggestion=(
                    f"Extend the deadline from {goal.timeframe_days} to about "
                    f"{new_days} days (~{new_weeks} weeks)."
                ),
                impact=f"Lowers the required weekly rate by ~{shortfall * 100:.0f}%.",
            )
        )
    else:
        adjustments.append(
            Adjustment(
                category="Timeframe",
                suggestion="Add usable weekly hours or budget first; a longer deadline alone cannot help if capacity is zero.",
                impact="Makes any schedule mathematically workable.",
            )
        )

    # More hours
    if goal.goal_type in {"learning", "fitness", "career", "creative", "custom"}:
        extra_hours = max(1.0, round(goal.weekly_hours * shortfall + 2, 1))
        adjustments.append(
            Adjustment(
                category="Time / earning capacity",
                suggestion=(
                    f"Increase focused weekly hours by ~{extra_hours:g} "
                    f"(from {goal.weekly_hours:g} toward {goal.weekly_hours + extra_hours:g})."
                ),
                impact="Raises weekly capacity to better match the required rate.",
            )
        )
    else:
        # financial: more earning or saving
        extra_save = max(25.0, needed * shortfall)
        adjustments.append(
            Adjustment(
                category="Spending",
                suggestion=(
                    f"Cut discretionary spending by about ${extra_save:,.0f}/week, "
                    f"or automate that amount into savings."
                ),
                impact=f"Closes roughly {min(100, shortfall * 100):.0f}% of the weekly gap.",
            )
        )
        adjustments.append(
            Adjustment(
                category="Earning",
                suggestion=(
                    f"Add ~{max(2, int(extra_save / 20))} hours of paid side work "
                    f"(~${extra_save:,.0f}/week at $20/hr) dedicated only to this goal."
                ),
                impact="Increases inflow without only relying on cuts.",
            )
        )

    if goal.goal_type == "financial":
        adjustments.append(
            Adjustment(
                category="Target",
                suggestion=(
                    f"Or lower the target from {goal.target_value:g} toward "
                    f"{goal.start_value + needed * capacity_score * _weeks_in_timeframe(goal.timeframe_days):,.0f} "
                    f"{goal.unit} for this timeframe, then stage a second goal."
                ),
                impact="Makes phase 1 achievable and builds confidence.",
            )
        )
    else:
        adjustments.append(
            Adjustment(
                category="Scope",
                suggestion=(
                    "Split the goal into a smaller MVP outcome for this timeframe, "
                    "then chain a follow-up goal for the remainder."
                ),
                impact="Preserves momentum when full target exceeds capacity.",
            )
        )

    if goal.weekly_budget > 0 and goal.goal_type != "financial":
        adjustments.append(
            Adjustment(
                category="Spending",
                suggestion=(
                    "Redirect budget from low-ROI tools toward coaching, templates, "
                    "or automation that multiplies hourly output."
                ),
                impact="Improves progress per hour rather than raw spend.",
            )
        )

    return adjustments


def analyze_goal(goal: GoalInput) -> PlanResult:
    errors = goal.validate()
    if errors:
        raise ValueError("; ".join(errors))

    gap = goal.target_value - goal.start_value
    direction = "increase" if gap > 0 else "decrease"
    absolute_gap = abs(gap)
    weeks = _weeks_in_timeframe(goal.timeframe_days)
    weekly_rate = gap / weeks
    daily_rate = gap / goal.timeframe_days

    capacity_score, capacity_note = _estimate_capacity(goal, weekly_rate)
    # Feasible if capacity covers required rate (with small tolerance)
    feasible = capacity_score >= 0.95 and (
        goal.weekly_hours > 0 or goal.weekly_budget > 0
    )

    # Special case: pure financial with budget covering rate
    if goal.goal_type == "financial" and goal.weekly_budget >= abs(weekly_rate) * 0.95:
        feasible = True
        capacity_score = max(capacity_score, goal.weekly_budget / max(abs(weekly_rate), 1e-9))

    type_meta = GOAL_TYPES[goal.goal_type]
    gap_analysis = [
        f"Starting point: {goal.start_value:g} {goal.unit}.",
        f"Target outcome: {goal.target_value:g} {goal.unit}.",
        f"Gap to close: {absolute_gap:g} {goal.unit} ({direction}).",
        f"Timeframe: {goal.timeframe_days} days (~{weeks:.1f} weeks).",
        f"Required pace: {abs(weekly_rate):,.2f} {goal.unit} {type_meta['rate_label']} "
        f"({abs(daily_rate):,.2f} per day).",
        f"Resources on hand: {goal.weekly_hours:g} h/week, ${goal.weekly_budget:,.2f}/week budget.",
        capacity_note,
    ]
    if goal.start_description:
        gap_analysis.insert(1, f"Starting state description: {goal.start_description}")
    if goal.target_description:
        gap_analysis.insert(
            2 if goal.start_description else 1,
            f"Target description: {goal.target_description}",
        )
    if goal.constraints:
        gap_analysis.append(f"Constraint noted: {goal.constraints}")
    if goal.notes:
        gap_analysis.append(f"Context: {goal.notes}")

    warnings: list[str] = []
    if goal.timeframe_days < 7 and absolute_gap > 0:
        warnings.append("Very short timeframe — daily discipline will dominate.")
    if capacity_score < 0.5:
        warnings.append("Capacity is well below the required rate; plan is not currently feasible.")
    elif capacity_score < 0.95:
        warnings.append("Capacity is slightly below the required rate; expect strain or slippage.")
    if goal.weekly_hours == 0 and goal.weekly_budget == 0:
        warnings.append("No hours or budget listed — add resources so feasibility can be judged.")
    if direction == "decrease" and goal.goal_type == "fitness":
        warnings.append("For reduction goals, prioritize sustainable deficit and recovery over crash pacing.")

    if feasible:
        summary = (
            f"“{goal.title}” looks achievable. Close a gap of {absolute_gap:g} {goal.unit} "
            f"at about {abs(weekly_rate):,.2f} {goal.unit}/week over {goal.timeframe_days} days."
        )
    else:
        summary = (
            f"“{goal.title}” is not feasible with the resources listed. "
            f"You need ~{abs(weekly_rate):,.2f} {goal.unit}/week but estimated capacity "
            f"covers only ~{capacity_score * 100:.0f}% of that rate. Adjust spending, earning, "
            f"hours, scope, or the deadline."
        )

    milestones = _build_milestones(goal, weekly_rate)
    steps = _build_steps(goal, weekly_rate, feasible)
    adjustments = _suggest_adjustments(goal, weekly_rate, capacity_score)

    metrics = {
        "start_value": goal.start_value,
        "target_value": goal.target_value,
        "start_description": goal.start_description,
        "target_description": goal.target_description,
        "unit": goal.unit,
        "gap": gap,
        "absolute_gap": absolute_gap,
        "direction": direction,
        "timeframe_days": goal.timeframe_days,
        "weeks": round(weeks, 2),
        "weekly_rate_required": round(weekly_rate, 4),
        "daily_rate_required": round(daily_rate, 4),
        "capacity_score": round(capacity_score, 4),
        "capacity_pct": round(min(capacity_score, 2.0) * 100, 1),
        "weekly_hours": goal.weekly_hours,
        "weekly_budget": goal.weekly_budget,
        "goal_type": goal.goal_type,
        "goal_type_label": type_meta["label"],
        "feasible": feasible,
    }

    return PlanResult(
        feasible=feasible,
        gap=gap,
        direction=direction,
        absolute_gap=absolute_gap,
        weekly_rate_required=weekly_rate,
        daily_rate_required=daily_rate,
        capacity_score=capacity_score,
        capacity_note=capacity_note,
        summary=summary,
        gap_analysis=gap_analysis,
        milestones=milestones,
        steps=steps,
        adjustments=adjustments,
        warnings=warnings,
        metrics=metrics,
    )


def plan_to_dict(plan: PlanResult) -> dict[str, Any]:
    return {
        "feasible": plan.feasible,
        "summary": plan.summary,
        "gap_analysis": plan.gap_analysis,
        "warnings": plan.warnings,
        "metrics": plan.metrics,
        "capacity_note": plan.capacity_note,
        "steps": plan.steps,
        "milestones": [
            {
                "week": m.week,
                "date_label": m.date_label,
                "target_value": m.target_value,
                "focus": m.focus,
                "actions": m.actions,
            }
            for m in plan.milestones
        ],
        "adjustments": [
            {
                "category": a.category,
                "suggestion": a.suggestion,
                "impact": a.impact,
            }
            for a in plan.adjustments
        ],
    }


def slugify(text: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "-", text.strip().lower()).strip("-")
    return s[:48] or "goal"
