import json
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from System.swarm_dsh_wct_bridge import BridgeError, HANDOFF, HarnessClient, ORNITH, dispatch, job_prompt, status


class FakeClient:
    def __init__(self, root):
        self.root, self.calls, self.running, self.fail = root, [], False, False

    def call(self, method, payload, rpc_id=None):
        self.calls.append((method, payload))
        if method == "session.list":
            return {"items": [{"sessionId": "s", "cwd": str(self.root), "running": self.running,
                              "projections": {"asOfSeq": 7}}]}
        if method == "session.models":
            return {"current": {"provider": "local-ollama", "model": ORNITH}, "routable": True}
        if method == "session.history":
            return {"events": [{"event": {"type": "turn/end", "data": {"reason": {"kind": "max-tokens"}}}}], "hasMore": True}
        if self.fail:
            raise TimeoutError("uncertain POST")
        return {"accepted": True}


@pytest.fixture
def root(tmp_path):
    path = tmp_path / HANDOFF
    path.parent.mkdir()
    path.write_text("# WCT\n### Start here: ORNITH-01 / callback\nFix callback.\n"
                    "### ORNITH-02 / audio\nTest noise.\n## OLD HISTORY\nNot a current assignment.\n")
    return tmp_path


def test_prompt_selects_one_canonical_job(root):
    prompt = job_prompt(root, ["ORNITH-01"])
    assert "Fix callback." in prompt
    assert "Test noise." not in prompt and "Not a current assignment." not in prompt
    for jobs in ([], ["ORNITH-99"], ["ORNITH-01", "ORNITH-01"]):
        with pytest.raises(BridgeError):
            job_prompt(root, jobs)


def test_dispatch_is_durable_and_never_reports_completion(root):
    client = FakeClient(root)
    assert dispatch(client, root, "s", ["ORNITH-01"])["status"] == "accepted_not_completed"
    assert dispatch(client, root, "s", ["ORNITH-01"])["status"] == "not_resent"
    assert len([c for c in client.calls if c[0] == "session.prompt"]) == 1
    rows = [json.loads(line) for line in next((root / ".sifta_state/dsh_wct").glob("*.jsonl")).read_text().splitlines()]
    assert [row["status"] for row in rows] == ["prepared", "accepted_not_completed"]


def test_uncertain_delivery_is_not_retried(root):
    client = FakeClient(root)
    client.fail = True
    with pytest.raises(BridgeError, match="uncertain"):
        dispatch(client, root, "s", ["ORNITH-01"])
    assert dispatch(client, root, "s", ["ORNITH-01"])["status"] == "not_resent"


def test_busy_wrong_workspace_and_cloud_model_are_refused(root):
    client = FakeClient(root)
    client.running = True
    with pytest.raises(BridgeError, match="busy"):
        dispatch(client, root, "s", ["ORNITH-01"])
    client.running = False
    client.root = root / "other"
    with pytest.raises(BridgeError, match="workspace"):
        dispatch(client, root, "s", ["ORNITH-01"])
    client.root = root
    original = client.call
    client.call = lambda method, payload, **kw: ({"current": {"provider": "cloud"}, "routable": True}
                                               if method == "session.models" else original(method, payload, **kw))
    with pytest.raises(BridgeError, match="local Ornith"):
        dispatch(client, root, "s", ["ORNITH-01"])
    assert not any(c[0] == "session.prompt" for c in client.calls)


def test_status_does_not_promote_max_tokens_to_success(root):
    result = status(FakeClient(root), root, "s")
    assert result["last_turn_reason"] == "max-tokens"
    assert "separate verification" in result["verification"]


@pytest.mark.parametrize("url", ["https://example.com", "http://localhost:3080", "http://127.0.0.1/x",
    "http://user@127.0.0.1:3080", "http://127.0.0.1:3080?token=secret"])
def test_remote_or_credential_origins_refused(url):
    with pytest.raises(BridgeError):
        HarnessClient(url)


def test_real_cli_host_transport_keyless_snapshot(root):
    client = FakeClient(root)
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            assert self.path == "/api/" + body["method"]
            value = client.call(body["method"], body["payload"])
            raw = json.dumps({"type": "server-response", "rpcId": body["rpcId"],
                              "result": {"ok": True, "value": value}}).encode()
            self.send_response(200)
            self.end_headers()
            self.wfile.write(raw)

        def log_message(self, *args):
            pass
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    launcher = Path(__file__).parents[1] / "deepseek-harness-master/scripts/sifta-wct.py"
    command = [sys.executable, str(launcher), "dispatch", "--root", str(root), "--session", "s",
               "--url", f"http://127.0.0.1:{server.server_port}"]
    try:
        outputs = [subprocess.run(command, capture_output=True, text=True, timeout=15, check=True).stdout for _ in range(2)]
        # Stable user-visible snapshot from the real adapter entrypoint, no model/key.
        assert [json.loads(output)["status"] for output in outputs] == ["accepted_not_completed", "not_resent"]
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=5)
