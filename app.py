#!/usr/bin/env python3
"""
Personal Goal Planner — Python web app.
Stores plans in local text files under data/ for privacy and full user control.
"""

from __future__ import annotations

import json
import mimetypes
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from goal_engine import GOAL_TYPES, analyze_goal, parse_goal_payload, plan_to_dict
from storage import delete_goal, ensure_dirs, get_goal, list_goals, save_goal

HOST = "0.0.0.0"
PORT = 8080
ROOT = Path(__file__).resolve().parent
STATIC = ROOT / "static"


class GoalHandler(BaseHTTPRequestHandler):
    server_version = "GoalPlanner/1.0"

    def log_message(self, fmt: str, *args: Any) -> None:
        # Quieter logs; still useful for debugging
        print(f"[{self.log_date_time_string()}] {self.address_string()} {fmt % args}")

    def _send(self, code: int, body: bytes, content_type: str, extra_headers: dict | None = None) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        if extra_headers:
            for k, v in extra_headers.items():
                self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _json(self, code: int, payload: Any) -> None:
        raw = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self._send(code, raw, "application/json; charset=utf-8")

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0:
            return {}
        raw = self.rfile.read(length)
        try:
            data = json.loads(raw.decode("utf-8"))
            return data if isinstance(data, dict) else {}
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON body: {exc}") from exc

    def _serve_static(self, rel: str) -> None:
        if rel in ("", "/"):
            path = STATIC / "index.html"
        else:
            clean = rel.lstrip("/")
            path = (STATIC / clean).resolve()
            try:
                path.relative_to(STATIC.resolve())
            except ValueError:
                self._json(403, {"error": "Forbidden"})
                return

        if not path.is_file():
            self._json(404, {"error": "Not found"})
            return

        ctype = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
        if path.suffix == ".html":
            ctype = "text/html; charset=utf-8"
        elif path.suffix == ".css":
            ctype = "text/css; charset=utf-8"
        elif path.suffix == ".js":
            ctype = "application/javascript; charset=utf-8"
        body = path.read_bytes()
        self._send(200, body, ctype)

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path

        try:
            if path == "/api/health":
                self._json(200, {"ok": True, "service": "goal-planner"})
                return

            if path == "/api/meta":
                self._json(
                    200,
                    {
                        "goal_types": {
                            k: {"label": v["label"], "default_unit": v["default_unit"]}
                            for k, v in GOAL_TYPES.items()
                        },
                        "storage": "Local text files under data/goals/",
                    },
                )
                return

            if path == "/api/goals":
                self._json(200, {"goals": list_goals()})
                return

            if path.startswith("/api/goals/"):
                goal_id = path[len("/api/goals/") :].strip("/")
                if not goal_id:
                    self._json(400, {"error": "Missing goal id"})
                    return
                # optional ?raw=1 for text download
                qs = parse_qs(parsed.query)
                goal = get_goal(goal_id)
                if not goal:
                    self._json(404, {"error": "Goal not found"})
                    return
                if qs.get("raw", ["0"])[0] in ("1", "true", "yes"):
                    text = goal.get("raw_text") or ""
                    self._send(
                        200,
                        text.encode("utf-8"),
                        "text/plain; charset=utf-8",
                        {
                            "Content-Disposition": f'attachment; filename="{goal.get("filename", "goal.txt")}"'
                        },
                    )
                    return
                # strip raw_text from JSON response for size
                out = {k: v for k, v in goal.items() if k != "raw_text"}
                self._json(200, out)
                return

            self._serve_static(path)
        except Exception as exc:  # noqa: BLE001
            traceback.print_exc()
            self._json(500, {"error": str(exc)})

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path
        try:
            if path == "/api/analyze":
                data = self._read_json()
                goal = parse_goal_payload(data)
                errors = goal.validate()
                if errors:
                    self._json(400, {"error": "; ".join(errors)})
                    return
                plan = analyze_goal(goal)
                persist = bool(data.get("save", True))
                meta = None
                if persist:
                    meta = save_goal(goal, plan)
                self._json(
                    200,
                    {
                        "plan": plan_to_dict(plan),
                        "saved": meta,
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
                    },
                )
                return

            self._json(404, {"error": "Not found"})
        except ValueError as exc:
            self._json(400, {"error": str(exc)})
        except Exception as exc:  # noqa: BLE001
            traceback.print_exc()
            self._json(500, {"error": str(exc)})

    def do_DELETE(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path
        try:
            if path.startswith("/api/goals/"):
                goal_id = path[len("/api/goals/") :].strip("/")
                if not goal_id:
                    self._json(400, {"error": "Missing goal id"})
                    return
                ok = delete_goal(goal_id)
                if not ok:
                    self._json(404, {"error": "Goal not found"})
                    return
                self._json(200, {"deleted": True, "id": goal_id})
                return
            self._json(404, {"error": "Not found"})
        except Exception as exc:  # noqa: BLE001
            traceback.print_exc()
            self._json(500, {"error": str(exc)})


def main() -> None:
    ensure_dirs()
    STATIC.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer((HOST, PORT), GoalHandler)
    print(f"Goal Planner listening on http://{HOST}:{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down")
        server.server_close()


if __name__ == "__main__":
    main()
