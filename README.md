# Goal Planner

Personal goal planner: gap analysis, required progress rates, step-by-step plans, and feasibility checks. Plans can be saved as local text files.

## Streamlit app

```bash
pip install -r requirements.txt
streamlit run streamlit_app.py
```

## Core (portable)

Same planning logic for Python, JS, and HTTP:

- `goal_engine.py` — Python core
- `core/goal_engine.js` — JavaScript core
- `main.py` — CLI (`python main.py --demo --pretty`)

## Project layout

| File | Role |
|------|------|
| `streamlit_app.py` | Streamlit UI |
| `goal_engine.py` | Planning engine |
| `storage.py` | Local text-file storage |
| `app.py` | Optional stdlib HTTP server |
| `requirements.txt` | Python deps |

## Deploy (Streamlit Community Cloud)

1. Push this repo to GitHub
2. In [share.streamlit.io](https://share.streamlit.io) → **New app**
3. Select the repo, branch `main`, main file `streamlit_app.py`
4. Deploy
