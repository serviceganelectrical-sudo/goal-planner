#!/usr/bin/env python3
"""
Portable entry point for the Goal Planner core.

Use this from the command line, scripts, serverless functions, or any host
that can run Python. Other platforms should call the same contract via:

  - Python:  analyze_goal(parse_goal_payload(data))
  - JS:      GoalEngine.analyze(data)
  - HTTP:    POST /api/analyze  { ...goal fields... }

Examples:
  python3 core/main.py --demo
  python3 core/main.py --json '{"title":"Save 5k","goal_type":"financial","start_value":500,"target_value":5000,"unit":"USD","timeframe_days":180,"weekly_hours":4,"weekly_budget":200}'
  echo '{...}' | python3 core/main.py --stdin
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Allow running from repo root or from core/
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from goal_engine import analyze_goal, parse_goal_payload, plan_to_dict  # noqa: E402


DEMO = {
    "title": "Emergency fund",
    "goal_type": "financial",
    "start_value": 500,
    "start_description": "Small cushion left after rent",
    "target_value": 5000,
    "target_description": "Three months of expenses in savings",
    "unit": "USD",
    "timeframe_days": 180,
    "weekly_hours": 4,
    "weekly_budget": 200,
    "notes": "No high-interest debt",
}


def run(data: dict) -> dict:
    """Main function — single call, full plan. Same contract as the HTTP API."""
    goal = parse_goal_payload(data)
    errors = goal.validate()
    if errors:
        return {"error": "; ".join(errors)}
    plan = analyze_goal(goal)
    return {
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Goal Planner core — portable main entry")
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("--demo", action="store_true", help="Run the built-in demo goal")
    src.add_argument("--json", type=str, help="Goal payload as a JSON string")
    src.add_argument("--stdin", action="store_true", help="Read goal JSON from stdin")
    src.add_argument("--file", type=str, help="Read goal JSON from a file")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output")
    args = parser.parse_args(argv)

    if args.demo:
        data = DEMO
    elif args.json:
        data = json.loads(args.json)
    elif args.stdin:
        data = json.load(sys.stdin)
    else:
        data = json.loads(Path(args.file).read_text(encoding="utf-8"))

    result = run(data)
    indent = 2 if args.pretty else None
    print(json.dumps(result, ensure_ascii=False, indent=indent))
    return 1 if "error" in result else 0


if __name__ == "__main__":
    raise SystemExit(main())
