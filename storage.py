"""
Local text-file storage for goals and plans.
All data lives under data/ as human-readable .txt files for privacy and control.
"""

from __future__ import annotations

import json
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from goal_engine import GoalInput, PlanResult, plan_to_dict, slugify

_DEFAULT_DATA = Path(__file__).resolve().parent / "data"
DATA_DIR = Path(os.environ.get("GOAL_DATA_DIR", str(_DEFAULT_DATA)))
GOALS_DIR = DATA_DIR / "goals"
INDEX_FILE = DATA_DIR / "index.txt"


def ensure_dirs() -> None:
    GOALS_DIR.mkdir(parents=True, exist_ok=True)
    if not INDEX_FILE.exists():
        INDEX_FILE.write_text(
            "# Goal Planner index\n"
            "# One line per goal: id | created_iso | title | filepath\n"
            "# Files are plain text under data/goals/ — yours to edit or delete.\n",
            encoding="utf-8",
        )


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _format_goal_file(
    goal_id: str,
    created: str,
    goal: GoalInput,
    plan: PlanResult,
) -> str:
    """Serialize a full goal + plan as a readable plain-text document."""
    lines: list[str] = [
        "GOAL PLANNER EXPORT",
        "=" * 60,
        f"id: {goal_id}",
        f"created: {created}",
        f"title: {goal.title}",
        f"goal_type: {goal.goal_type}",
        f"start_value: {goal.start_value}",
        f"start_description: {goal.start_description or '-'}",
        f"target_value: {goal.target_value}",
        f"target_description: {goal.target_description or '-'}",
        f"unit: {goal.unit}",
        f"timeframe_days: {goal.timeframe_days}",
        f"start_date: {goal.start_date}",
        f"weekly_hours: {goal.weekly_hours}",
        f"weekly_budget: {goal.weekly_budget}",
        f"constraints: {goal.constraints or '-'}",
        f"notes: {goal.notes or '-'}",
        "",
        "FEASIBILITY",
        "-" * 40,
        f"feasible: {'yes' if plan.feasible else 'no'}",
        f"summary: {plan.summary}",
        f"capacity_score: {plan.capacity_score:.4f}",
        f"weekly_rate_required: {plan.weekly_rate_required:.4f}",
        f"daily_rate_required: {plan.daily_rate_required:.4f}",
        "",
        "GAP ANALYSIS",
        "-" * 40,
    ]
    for item in plan.gap_analysis:
        lines.append(f"- {item}")

    if plan.warnings:
        lines.extend(["", "WARNINGS", "-" * 40])
        for w in plan.warnings:
            lines.append(f"! {w}")

    lines.extend(["", "STEP-BY-STEP PLAN", "-" * 40])
    for step in plan.steps:
        lines.append(f"{step['order']}. {step['title']}")
        lines.append(f"   {step['detail']}")

    lines.extend(["", "MILESTONES", "-" * 40])
    for m in plan.milestones:
        lines.append(
            f"Week {m.week} ({m.date_label}): reach {m.target_value:g} {goal.unit}"
        )
        lines.append(f"   Focus: {m.focus}")
        for a in m.actions:
            lines.append(f"   * {a}")

    lines.extend(["", "ADJUSTMENTS", "-" * 40])
    for adj in plan.adjustments:
        lines.append(f"[{adj.category}] {adj.suggestion}")
        lines.append(f"   Impact: {adj.impact}")

    # Machine-readable block for reload
    payload = {
        "id": goal_id,
        "created": created,
        "goal": {
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
        },
        "plan": plan_to_dict(plan),
    }
    lines.extend(
        [
            "",
            "JSON_PAYLOAD_BEGIN",
            json.dumps(payload, indent=2, ensure_ascii=False),
            "JSON_PAYLOAD_END",
            "",
        ]
    )
    return "\n".join(lines)


def _extract_json_payload(text: str) -> dict[str, Any] | None:
    match = re.search(
        r"JSON_PAYLOAD_BEGIN\s*(\{.*?\})\s*JSON_PAYLOAD_END",
        text,
        re.DOTALL,
    )
    if not match:
        return None
    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError:
        return None


def save_goal(goal: GoalInput, plan: PlanResult) -> dict[str, Any]:
    ensure_dirs()
    goal_id = uuid.uuid4().hex[:12]
    created = _utc_now()
    filename = f"{created[:10]}_{slugify(goal.title)}_{goal_id}.txt"
    path = GOALS_DIR / filename
    content = _format_goal_file(goal_id, created, goal, plan)
    path.write_text(content, encoding="utf-8")

    with INDEX_FILE.open("a", encoding="utf-8") as fh:
        fh.write(f"{goal_id} | {created} | {goal.title} | goals/{filename}\n")

    return {
        "id": goal_id,
        "created": created,
        "filename": filename,
        "path": str(path.relative_to(DATA_DIR)),
        "title": goal.title,
        "feasible": plan.feasible,
    }


def list_goals() -> list[dict[str, Any]]:
    ensure_dirs()
    items: list[dict[str, Any]] = []
    for path in sorted(GOALS_DIR.glob("*.txt"), reverse=True):
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        payload = _extract_json_payload(text)
        if payload:
            items.append(
                {
                    "id": payload.get("id"),
                    "created": payload.get("created"),
                    "title": payload.get("goal", {}).get("title") or path.stem,
                    "feasible": payload.get("plan", {}).get("feasible"),
                    "filename": path.name,
                    "path": f"goals/{path.name}",
                    "metrics": payload.get("plan", {}).get("metrics", {}),
                    "summary": payload.get("plan", {}).get("summary", ""),
                }
            )
        else:
            items.append(
                {
                    "id": path.stem,
                    "created": "",
                    "title": path.stem,
                    "feasible": None,
                    "filename": path.name,
                    "path": f"goals/{path.name}",
                    "metrics": {},
                    "summary": "",
                }
            )
    return items


def get_goal(goal_id: str) -> dict[str, Any] | None:
    ensure_dirs()
    for path in GOALS_DIR.glob("*.txt"):
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        payload = _extract_json_payload(text)
        if not payload:
            continue
        if payload.get("id") == goal_id or path.stem.endswith(goal_id):
            payload["filename"] = path.name
            payload["path"] = f"goals/{path.name}"
            payload["raw_text"] = text
            return payload
    return None


def delete_goal(goal_id: str) -> bool:
    ensure_dirs()
    deleted = False
    for path in list(GOALS_DIR.glob("*.txt")):
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        payload = _extract_json_payload(text)
        match = False
        if payload and payload.get("id") == goal_id:
            match = True
        elif path.stem.endswith(goal_id) or goal_id in path.name:
            match = True
        if match:
            path.unlink(missing_ok=True)
            deleted = True
            break

    if deleted and INDEX_FILE.exists():
        lines = INDEX_FILE.read_text(encoding="utf-8").splitlines()
        kept = [ln for ln in lines if not ln.startswith(f"{goal_id} |")]
        INDEX_FILE.write_text("\n".join(kept) + ("\n" if kept else ""), encoding="utf-8")
    return deleted


def read_raw_file(rel_path: str) -> str | None:
    """Read a file under data/ by relative path (no path traversal)."""
    ensure_dirs()
    # Only allow files under data/
    candidate = (DATA_DIR / rel_path).resolve()
    try:
        candidate.relative_to(DATA_DIR.resolve())
    except ValueError:
        return None
    if not candidate.is_file():
        # try goals/
        candidate = (GOALS_DIR / Path(rel_path).name).resolve()
        try:
            candidate.relative_to(DATA_DIR.resolve())
        except ValueError:
            return None
        if not candidate.is_file():
            return None
    return candidate.read_text(encoding="utf-8")
