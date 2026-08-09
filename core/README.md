# Goal Planner — portable core

One brain, many frontends. You do **not** need to reimplement planning for each platform.

## Main function

| Platform | Call |
|----------|------|
| **Python** | `from goal_engine import parse_goal_payload, analyze_goal` then `analyze_goal(parse_goal_payload(data))` — or `python3 main.py --json '...'` |
| **JavaScript / web / React Native / Node** | `GoalEngine.analyze(data)` from `goal_engine.js` |
| **Any HTTP client (mobile, desktop, Zapier…)** | `POST /api/analyze` with the same JSON body |

## Input (JSON)

```json
{
  "title": "Emergency fund",
  "goal_type": "financial",
  "start_value": 500,
  "start_description": "optional text",
  "target_value": 5000,
  "target_description": "optional text",
  "unit": "USD",
  "timeframe_days": 180,
  "start_date": "2026-08-09",
  "weekly_hours": 4,
  "weekly_budget": 200,
  "constraints": "",
  "notes": ""
}
```

`goal_type`: `financial` | `fitness` | `learning` | `career` | `creative` | `custom`

## Output

```json
{
  "goal": { "...echo of inputs..." },
  "plan": {
    "feasible": true,
    "summary": "...",
    "gap_analysis": ["..."],
    "warnings": [],
    "metrics": { "gap": 4500, "weekly_rate_required": 175, "capacity_pct": 130.3, "...": "..." },
    "steps": [{ "order": 1, "title": "...", "detail": "..." }],
    "milestones": [{ "week": 3, "date_label": "...", "target_value": 1025, "focus": "...", "actions": [] }],
    "adjustments": [{ "category": "...", "suggestion": "...", "impact": "..." }]
  }
}
```

On validation failure: `{ "error": "..." }`.

## Files

| File | Use |
|------|-----|
| `../goal_engine.py` | Source of truth (Python) |
| `goal_engine.js` / `goal_engine.cjs` | Same logic for browser / Node / hybrid apps |
| `main.py` | CLI / serverless entry (`--demo`, `--json`, `--stdin`, `--file`) |

## What to build per platform

You only build **UI + I/O**. Always call the main function above.

1. **Web** — already shipped (`static/` + optional Python API for text-file saves)
2. **Mobile app** — form screens → `GoalEngine.analyze` (JS) or `POST /api/analyze`
3. **Desktop** — same as web or Electron wrapping the JS core
4. **CLI / automation** — `python3 main.py --json '...'`

## Quick tests

```bash
python3 main.py --demo --pretty
node -e "console.log(require('./core/goal_engine.cjs').analyze({title:'x',start_value:0,target_value:10,timeframe_days:70,weekly_hours:5,weekly_budget:100,goal_type:'financial',unit:'USD'}).plan.summary)"
```
