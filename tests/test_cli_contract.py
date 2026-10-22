"""Opt-in real CLI contract check against a local canned Responses endpoint.

Set CODEX_CONTRACT_BIN to test an installed CLI. No login or model service is used.
"""

import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from pytest_codex.runner import execute


@pytest.mark.skipif(
    not os.environ.get("CODEX_CONTRACT_BIN"), reason="opt-in installed CLI contract"
)
def test_installed_cli_jsonl_contract(tmp_path, monkeypatch):
    requests = []

    class Endpoint(BaseHTTPRequestHandler):
        def do_POST(self):
            assert self.path == "/v1/responses"
            requests.append(json.loads(self.rfile.read(int(self.headers["Content-Length"]))))
            message = {
                "id": "msg_contract",
                "type": "message",
                "role": "assistant",
                "status": "completed",
                "content": [{"type": "output_text", "text": "contract-ok"}],
            }
            events = [
                {"type": "response.created", "response": {"id": "resp_contract"}},
                {
                    "type": "response.output_item.added",
                    "output_index": 0,
                    "item": {
                        "id": "msg_contract",
                        "type": "message",
                        "role": "assistant",
                        "content": [],
                    },
                },
                {
                    "type": "response.output_text.delta",
                    "item_id": "msg_contract",
                    "output_index": 0,
                    "content_index": 0,
                    "delta": "contract-ok",
                },
                {"type": "response.output_item.done", "output_index": 0, "item": message},
                {
                    "type": "response.completed",
                    "response": {
                        "id": "resp_contract",
                        "status": "completed",
                        "output": [message],
                        "usage": {"input_tokens": 7, "output_tokens": 2, "total_tokens": 9},
                    },
                },
            ]
            data = "".join(
                f"event: {event['type']}\ndata: {json.dumps(event)}\n\n" for event in events
            ).encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Endpoint)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    home = tmp_path / "empty-home"
    home.mkdir()
    monkeypatch.setenv("CODEX_HOME", str(home))
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    project = tmp_path / "project"
    project.mkdir()
    try:
        run = execute(
            "Reply contract-ok.",
            project,
            codex_bin=os.environ["CODEX_CONTRACT_BIN"],
            model="local-contract",
            sandbox="read-only",
            timeout=45,
            config={
                "model_provider": "contract",
                "model_providers.contract": {
                    "name": "Local contract fixture",
                    "base_url": f"http://127.0.0.1:{server.server_port}/v1",
                    "wire_api": "responses",
                    "requires_openai_auth": False,
                    "supports_websockets": False,
                    "request_max_retries": 0,
                },
                "features.shell_tool": False,
            },
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
    assert len(requests) == 1
    assert requests[0]["model"] == "local-contract"
    assert run.succeeded, run
    assert run.final_message == "contract-ok", run
    assert run.tokens.total == 9, run
