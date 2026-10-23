"""Local, read-only Desktop rule panel. No model calls or runtime dependencies."""

from __future__ import annotations

import argparse
import hmac
import json
import os
import secrets
import threading
import webbrowser
from copy import deepcopy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .compare import compare_reports
from .dashboard_data import evaluate_rules, read_agents, recent_tasks, suggest_rules, validate_rules
from .desktop import _portable

MAX_BODY = 4 * 1024 * 1024
ASSETS = {
    "/": ("panel.html", "text/html"),
    "/panel.js": ("panel.js", "text/javascript"),
    "/panel.css": ("panel.css", "text/css"),
}


class PanelState:
    def __init__(self, project, sessions, limit):
        self.project = Path(project).resolve()
        self.sessions = Path(sessions).resolve()
        if not self.project.is_dir() or type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError("Select an existing project and 1-100 tasks")
        self.limit = limit
        self.rules = {"commands": [], "files": []}
        self.cached = None
        self.lock = threading.RLock()

    def refresh(self):
        with self.lock:
            self.cached = recent_tasks(self.sessions, self.project, limit=self.limit)
            agents = read_agents(self.project)
            self.cached.update(
                project=self.project.name, agents=agents, suggestions=suggest_rules(agents["text"])
            )
            return self.snapshot()

    def snapshot(self):
        with self.lock:
            if self.cached is None:
                return self.refresh()
            result = deepcopy(self.cached)
            result["rules"] = deepcopy(self.rules)
            for task in result["tasks"]:
                task["check"] = evaluate_rules(task, self.rules)
            return result

    def apply(self, rules):
        rules = validate_rules(rules)
        with self.lock:
            self.rules = rules
            return self.snapshot()


class PanelServer(ThreadingHTTPServer):
    daemon_threads = True


def make_server(project, sessions, *, limit=20, port=0):
    state = PanelState(project, sessions, limit)
    capability = secrets.token_urlsafe(32)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            # Avoid writing requests, history or capabilities to access logs.
            pass

        def _send(self, code, raw, content_type="application/json"):
            self.send_response(code)
            self.send_header("Content-Type", content_type + "; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header(
                "Content-Security-Policy",
                "default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'",
            )
            self.end_headers()
            self.wfile.write(raw)

        def _json(self, code, data):
            self._send(code, json.dumps(data, ensure_ascii=False, allow_nan=False).encode("utf-8"))

        def _access(self, api=False):
            expected = f"127.0.0.1:{self.server.server_port}"
            if (
                self.headers.get("Host") != expected
                or self.headers.get("Origin", "http://" + expected) != "http://" + expected
            ):
                self._json(403, {"error": "仅允许本机同源访问"})
                return False
            if api and not hmac.compare_digest(
                self.headers.get("X-Panel-Token", "").encode(), capability.encode()
            ):
                self._json(403, {"error": "请使用启动时的完整本地链接打开面板"})
                return False
            return True

        def do_GET(self):
            if not self._access(self.path.startswith("/api/")):
                return
            if self.path in ASSETS:
                name, content_type = ASSETS[self.path]
                self._send(
                    200, (Path(__file__).parent / "panel_assets" / name).read_bytes(), content_type
                )
            elif self.path == "/api/state":
                self._json(200, state.snapshot())
            else:
                self._json(404, {"error": "没有此接口"})

        def do_POST(self):
            if not self._access(api=True):
                return
            if self.path not in {"/api/rules", "/api/refresh", "/api/compare"}:
                self._json(404, {"error": "没有此接口"})
                return
            if self.headers.get("Content-Type", "").split(";", 1)[0].strip() != "application/json":
                self._json(415, {"error": "需要 JSON"})
                return
            length = self.headers.get("Content-Length", "")
            if not length.isdigit() or not 0 < int(length) <= MAX_BODY:
                self._json(413, {"error": "请求大小需小于 4 MiB"})
                return
            try:
                self.connection.settimeout(5)
                data = json.loads(self.rfile.read(int(length)).decode("utf-8"))
                if self.path == "/api/rules":
                    response = state.apply(data)
                elif self.path == "/api/refresh":
                    if data != {}:
                        raise ValueError("Refresh cannot change roots")
                    response = state.refresh()
                else:
                    if not isinstance(data, dict) or set(data) != {
                        "baseline",
                        "candidate",
                        "factor",
                    }:
                        raise ValueError("Comparison needs two results reports and one factor")
                    response = compare_reports(
                        data["baseline"], data["candidate"], factor=data["factor"]
                    )
                    response["context"] = {
                        k: response["context"][k] for k in ("python", "platform", "plugin_version")
                    }
                    response = _portable(response, str(state.project))
                self._json(200, response)
            except (OSError, ValueError, TypeError, KeyError, AttributeError, RecursionError):
                self._json(
                    400,
                    {
                        "error": "无法检查：请核对规则或匹配的真实运行结果 JSON。桌面历史观察不能当作新模型回归样本。"
                    },
                )

    server = PanelServer(("127.0.0.1", port), Handler)
    server.capability = capability
    return server


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--project", required=True, type=Path, help="only read history attributed to this project"
    )
    parser.add_argument(
        "--sessions",
        type=Path,
        default=Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))) / "sessions",
    )
    parser.add_argument("--limit", type=int, default=20, help="1-100 recent turns (default 20)")
    parser.add_argument(
        "--port", type=int, default=0, help="loopback port; default chooses a free port"
    )
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args(argv)
    try:
        server = make_server(args.project, args.sessions, limit=args.limit, port=args.port)
    except (OSError, ValueError, OverflowError):
        parser.exit(2, "Cannot start panel: check project, task limit and available port.\n")
    url = f"http://127.0.0.1:{server.server_port}/#{server.capability}"
    print("Local panel (private, keep this window open): " + url, flush=True)
    if not args.no_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
