# Goal Planner

Personal goal planner: gap analysis, required progress rates, step-by-step plans, and feasibility checks. Plans can be saved as local text files.

## Streamlit app

```bash
pip install -r requirements.txt
streamlit run streamlit_app.py
```

## Core (portable)

Same planning logic for Python, CLI, and HTTP:

- `goal_engine.py` — public Python API
- `ge_models.py` / `ge_capacity.py` / `ge_plan.py` — engine internals
- `main.py` — CLI (`python main.py --demo --pretty`)

## Project layout

| File | Role |
|------|------|
| `streamlit_app.py` | Streamlit UI |
| `streamlit_helpers.py` | Streamlit UI helpers |
| `goal_engine.py` | Planning engine (public API) |
| `ge_models.py` / `ge_capacity.py` / `ge_plan.py` | Engine internals |
| `storage.py` | Local text-file storage |
| `app.py` | Optional stdlib HTTP server |
| `requirements.txt` | Python deps |

## Deploy (Streamlit Community Cloud)

1. Open [share.streamlit.io](https://share.streamlit.io) → **New app**
2. Select repo `serviceganelectrical-sudo/goal-planner`, branch `main`
3. Main file path: `streamlit_app.py`
4. Deploy
