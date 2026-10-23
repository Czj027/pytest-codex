import http.client
import json
import threading

import pytest

from pytest_codex.dashboard import make_server


@pytest.fixture
def panel(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    sessions = tmp_path / "sessions"
    sessions.mkdir()
    rows = [
        {"type": "session_meta", "payload": {"cwd": str(project)}},
        {"type": "event_msg", "payload": {"type": "task_started", "turn_id": "demo"}},
        {"type": "event_msg", "payload": {"type": "task_complete", "turn_id": "demo"}},
    ]
    (sessions / "rollout-demo.jsonl").write_text(
        "\n".join(json.dumps(r) for r in rows), encoding="utf-8"
    )
    server = make_server(project, sessions)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=5)


def request(server, path, *, method="GET", data=None, auth=True, headers=None):
    conn = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=5)
    fields = {"X-Panel-Token": server.capability} if auth else {}
    if data is not None:
        fields["Content-Type"] = "application/json"
    fields.update(headers or {})
    conn.request(method, path, body=json.dumps(data) if data is not None else None, headers=fields)
    response = conn.getresponse()
    result = response.status, dict(response.getheaders()), response.read()
    conn.close()
    return result


def test_loopback_only_and_authentication_for_all_data(panel):
    assert panel.server_address[0] == "127.0.0.1"
    assert request(panel, "/api/state", auth=False)[0] == 403
    assert request(panel, "/api/state", headers={"X-Panel-Token": "wrong"})[0] == 403
    assert request(panel, "/api/state", headers={"X-Panel-Token": "\xff"})[0] == 403
    status, headers, raw = request(panel, "/api/state")
    assert status == 200 and json.loads(raw)["tasks"][0]["turn_id"] == "demo"
    assert headers["Cache-Control"] == "no-store"
    assert "Access-Control-Allow-Origin" not in headers
    assert request(panel, "/api/state", headers={"Origin": "https://evil.example"})[0] == 403
    assert request(panel, "/api/state", headers={"Host": "evil.example"})[0] == 403


def test_static_assets_and_no_arbitrary_file_endpoint(panel):
    status, headers, raw = request(panel, "/", auth=False)
    assert status == 200 and b"panel.js" in raw
    assert "default-src 'none'" in headers["Content-Security-Policy"]
    assert panel.capability.encode() not in raw
    assert request(panel, "/panel.js", auth=False)[0] == 200
    assert request(panel, "/panel.css", auth=False)[0] == 200
    assert request(panel, "/../../pyproject.toml", auth=False)[0] == 404
    assert request(panel, "/api/file?path=auth.json")[0] == 404


def test_rules_and_refresh_stay_in_memory(panel):
    rules = {"commands": ["pip install"], "files": []}
    status, _, raw = request(panel, "/api/rules", method="POST", data=rules)
    assert status == 200 and json.loads(raw)["tasks"][0]["check"]["status"] == "pass"
    assert request(panel, "/api/rules", method="POST", data={"path": "private"})[0] == 400
    assert request(panel, "/api/refresh", method="POST", data={})[0] == 200
    assert request(panel, "/api/refresh", method="POST", data={"project": "outside"})[0] == 400
    assert request(panel, "/api/rules", method="POST", data=rules, auth=False)[0] == 403


def test_request_body_limits_and_fresh_comparison_validation(panel):
    assert (
        request(
            panel,
            "/api/compare",
            method="POST",
            data={"baseline": {"schema": "desktop"}, "candidate": {}, "factor": "model"},
        )[0]
        == 400
    )
    assert (
        request(
            panel, "/api/rules", method="POST", data={}, headers={"Content-Type": "text/plain"}
        )[0]
        == 415
    )
    assert (
        request(
            panel,
            "/api/rules",
            method="POST",
            data={},
            headers={"Content-Length": str(5 * 1024 * 1024)},
        )[0]
        == 413
    )


def test_compare_reuses_existing_contract_and_retains_errors(panel):
    from test_compare import report

    before, after = report(), report("after", ("passed", "error", "failed"))
    result = request(
        panel,
        "/api/compare",
        method="POST",
        data={"baseline": before, "candidate": after, "factor": "model"},
    )
    assert result[0] == 200
    data = json.loads(result[2])
    assert data["cases"][0]["direction"] == "inconclusive"
    assert data["usage"]["baseline"]["cached_input_tokens"] == 240
