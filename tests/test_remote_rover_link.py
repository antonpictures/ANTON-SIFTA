import json
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from types import SimpleNamespace

import pytest

from System.stigmerobotics_remote_link import RemoteRoverLink


def enroll(link, name="david-car"):
    return link.pair(link.invite(name)["ticket"])


def sample(pair, sequence=0):
    return {"robot_id": pair["robot_id"], "connection_id": pair["connection_id"],
            "sequence": sequence, "captured_at": 1.0,
            "readings": {"mode": "manual", "stopped": True}}


def test_ticket_atomic_single_use(tmp_path):
    link = RemoteRoverLink(tmp_path)
    ticket = link.invite("david-car")["ticket"]
    def redeem(_):
        try:
            return RemoteRoverLink(tmp_path).pair(ticket)
        except PermissionError:
            return None
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(redeem, range(4)))
    assert sum(r is not None for r in results) == 1


def test_scope_replay_restart_and_revocation(tmp_path):
    link = RemoteRoverLink(tmp_path)
    a, b = enroll(link), enroll(link, "second-car")
    row = sample(a)
    assert link.receive(a["token"], row)["accepted"]
    restarted = RemoteRoverLink(tmp_path)
    assert restarted.receive(a["token"], row)["duplicate"]
    with pytest.raises(PermissionError):
        restarted.receive(b["token"], row)
    with pytest.raises(ValueError):
        restarted.receive(a["token"], {**row, "readings": {"stopped": False}})
    restarted.receive(a["token"], sample(a, 2))
    with pytest.raises(ValueError):
        restarted.receive(a["token"], row)
    link.invite("david-car")
    with pytest.raises(PermissionError):
        link.status(a["token"])


def test_ages_not_renewed_by_duplicate_and_no_motion(tmp_path):
    now = [1000.0]
    link = RemoteRoverLink(tmp_path, clock=lambda: now[0])
    p = enroll(link)
    assert link.status(p["token"])["state"] == "awaiting_telemetry"
    link.receive(p["token"], sample(p))
    view = link.status(p["token"])
    assert view["state"] == "online_unarmed"
    assert not view["motion_enabled"] and not view["capture_clock_verified"]
    now[0] += 16
    link.receive(p["token"], sample(p))
    assert link.status(p["token"])["state"] == "stale"
    now[0] += 43200
    with pytest.raises(PermissionError):
        link.status(p["token"])
    assert link.owner_status()[0]["state"] == "expired"
    public = json.dumps(link.owner_status())
    assert p["token"] not in public and "token_hash" not in public


@pytest.mark.parametrize("change", [
    {"sequence": True}, {"sequence": -1}, {"sequence": 2**63},
    {"captured_at": float("nan")}, {"captured_at": -1},
    {"readings": {}}, {"readings": {"voltage": float("inf")}},
    {"readings": {"x": "a" * 17000}}, {"command": "forward"},
])
def test_invalid_telemetry(tmp_path, change):
    link = RemoteRoverLink(tmp_path)
    p = enroll(link)
    with pytest.raises(ValueError):
        link.receive(p["token"], {**sample(p), **change})
    assert link.status(p["token"])["sequence"] == -1


def test_expired_invitation(tmp_path):
    now = [1.0]
    link = RemoteRoverLink(tmp_path, clock=lambda: now[0])
    ticket = link.invite("david-car")["ticket"]
    now[0] = 301
    with pytest.raises(PermissionError):
        link.pair(ticket)


def test_gateway_retries_exact_envelope_without_leaking_token(tmp_path):
    from System.stigmerobotics_remote_link import RemoteRoverGateway

    calls = []
    class Response:
        def read(self, _size):
            return b'{"accepted":true,"duplicate":true,"sequence":3}'
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return None
    class Opener:
        def open(self, request, timeout):
            calls.append((request.full_url, request.get_header("Authorization"), request.data))
            if len(calls) == 1:
                raise OSError("connection lost after send")
            return Response()

    gateway = RemoteRoverGateway(
        "https://stigmergicoin.com", token="secret-token", robot_id="david-car",
        connection_id="conn_1", opener=Opener())
    with pytest.raises(ConnectionError):
        gateway.send_telemetry(sequence=3, captured_at=10.0, readings={"stopped": True})
    assert gateway.send_telemetry(sequence=3, captured_at=10.0, readings={"stopped": True})["duplicate"]
    assert calls[0][2] == calls[1][2]
    assert "secret-token" not in calls[0][2].decode()
    with pytest.raises(ValueError):
        RemoteRoverGateway("http://example.test", token="x", robot_id="david-car", connection_id="conn_1")


def test_rover_chat_is_scoped_and_uses_existing_reply_stream(tmp_path, monkeypatch):
    from System import chorus_node_server as server
    from System import swarm_stigmergicode_command as owner
    from System import swarm_web_global_chat_gate as gate

    monkeypatch.setattr(server, "_REPO", tmp_path)
    monkeypatch.setattr(owner, "authenticate", lambda token: token == "owner-secret")
    monkeypatch.setattr(gate, "submit_web_message", lambda *args, **kwargs: {
        "accepted": True, "status": "queued", "turn_id": "turn-1", "session_id": "rover:david-car"})
    link = RemoteRoverLink(tmp_path / ".sifta_state")
    pair = enroll(link)
    result = []
    payload = json.dumps({"robot_id": "david-car", "connection_id": pair["connection_id"],
                          "request_id": "chat_1", "text": "Ce vezi?"}).encode()
    handler = SimpleNamespace(
        headers={"Host": "stigmergicoin.com", "Content-Length": str(len(payload)),
                 "Authorization": "Bearer " + pair["token"]},
        path="/api/rover/chat", rfile=BytesIO(payload),
        _respond=lambda status, value: result.append((status, value)))
    handler._read_json_body = lambda: server.ChorusHandler._read_json_body(handler)
    server.ChorusHandler._handle_rover_link(handler)
    assert result == [(200, {"accepted": True, "status": "queued", "turn_id": "turn-1",
                             "session_id": "rover:david-car", "robot_id": "david-car"})]
    result.clear()
    payload = json.dumps({"robot_id": "david-car", "connection_id": pair["connection_id"],
                          "request_id": "chat_2", "text": "/stigmergicode change everything"}).encode()
    handler.rfile = BytesIO(payload)
    handler.headers["Content-Length"] = str(len(payload))
    server.ChorusHandler._handle_rover_link(handler)
    assert result[0][0] == 403


def test_http_owner_separation_and_host_isolation(tmp_path, monkeypatch):
    from System import chorus_node_server as server
    from System import swarm_stigmergicode_command as owner
    monkeypatch.setattr(server, "_REPO", tmp_path)
    monkeypatch.setattr(owner, "authenticate", lambda token: token == "owner-secret")

    def request(action, payload, token="", host="stigmergicoin.com", cookie=""):
        body = json.dumps(payload).encode()
        result = []
        handler = SimpleNamespace(
            headers={"Host": host, "Content-Length": str(len(body)),
                     "Authorization": "Bearer " + token, "Cookie": cookie},
            path="/api/rover/" + action, rfile=BytesIO(body),
            _respond=lambda status, value: result.append((status, value)))
        handler._read_json_body = lambda: server.ChorusHandler._read_json_body(handler)
        server.ChorusHandler._handle_rover_link(handler)
        return result[0]

    assert request("invite", {"robot_id": "david-car"}, cookie="sifta_owner=owner-secret")[0] == 403
    assert request("invite", {"robot_id": "david-car"}, "owner-secret", "stigmergicode.com")[0] == 404
    status, invitation = request("invite", {"robot_id": "david-car"}, "owner-secret")
    assert status == 200
    status, pair = request("pair", {"ticket": invitation["ticket"]})
    assert status == 200
    assert request("invite", {"robot_id": "other"}, pair["token"])[0] == 403
    assert request("telemetry", sample(pair), "owner-secret")[0] == 403
    assert request("telemetry", sample(pair), pair["token"])[0] == 200
    assert request("status", {}, pair["token"])[1]["state"] == "online_unarmed"
    assert len(request("status", {}, "owner-secret")[1]["rovers"]) == 1


def test_real_http_routes_and_no_coding_authority(tmp_path, monkeypatch):
    import http.client
    from http.server import ThreadingHTTPServer
    import threading
    from System import chorus_node_server as server
    from System import swarm_stigmergicode_command as owner

    monkeypatch.setattr(server, "_REPO", tmp_path)
    monkeypatch.setattr(owner, "authenticate", lambda token: token == "owner-secret")
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.ChorusHandler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()

    def post(path, data, token="", host="stigmergicoin.com"):
        connection = http.client.HTTPConnection(*httpd.server_address, timeout=3)
        try:
            connection.request("POST", path, json.dumps(data), headers={
                "Host": host, "Authorization": "Bearer " + token,
                "Content-Type": "application/json"})
            response = connection.getresponse()
            return response.status, json.loads(response.read())
        finally:
            connection.close()

    def get(path, token="", host="stigmergicoin.com"):
        connection = http.client.HTTPConnection(*httpd.server_address, timeout=3)
        try:
            connection.request("GET", path, headers={
                "Host": host, "Authorization": "Bearer " + token})
            response = connection.getresponse()
            return response.status, json.loads(response.read())
        finally:
            connection.close()

    try:
        status, invitation = post("/api/rover/invite", {"robot_id": "david-car"}, "owner-secret")
        assert status == 200
        status, pair = post("/api/rover/pair", {"ticket": invitation["ticket"]})
        assert status == 200
        assert post("/api/rover/telemetry", sample(pair), pair["token"])[0] == 200
        status, arm = post("/api/rover/arm", {"robot_id": "david-car"}, "owner-secret")
        assert status == 200 and arm["scope"] == "rover.control"
        command = {"robot_id": "david-car", "connection_id": pair["connection_id"],
                   "command_id": "move_http", "linear_mm_s": 100,
                   "angular_mrad_s": 0, "timeout_ms": 250}
        assert post("/api/rover/command", command, arm["control_token"])[0] == 200
        assert get("/api/rover/commands?limit=1", arm["control_token"])[1]["commands"]
        assert post("/api/rover/status", {}, pair["token"])[1]["sequence"] == 0
        assert post("/api/stigmergicode", {"text": "/stigmergicode test"}, pair["token"])[0] == 403
        assert post("/api/rover/status", {}, pair["token"], "stigmergicode.com")[0] == 404
        assert post("/api/rover/telemetry", {"padding": "x" * 33000}, pair["token"])[0] == 413
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=3)


def test_control_lease_queue_claim_and_ack_are_separate(tmp_path):
    link = RemoteRoverLink(tmp_path)
    pair = enroll(link)
    arm = link.arm("david-car")
    assert arm["scope"] == "rover.control"
    command = {"robot_id": "david-car", "connection_id": pair["connection_id"],
               "command_id": "move_1", "linear_mm_s": 100,
               "angular_mrad_s": 0, "timeout_ms": 250}
    with pytest.raises(PermissionError):
        link.enqueue_command(pair["token"], command)
    assert link.enqueue_command(arm["control_token"], command)["accepted"]
    assert link.enqueue_command(arm["control_token"], command)["duplicate"]
    batch = link.poll_commands(arm["control_token"])
    ttl = batch["commands"][0].pop("valid_for_ms")
    assert 0 < ttl <= 2250
    assert batch["commands"] == [{"command_id": "move_1", "linear_mm_s": 100,
                                   "angular_mrad_s": 0, "timeout_ms": 250}]
    assert link.poll_commands(arm["control_token"])["commands"] == []
    assert link.ack_command(arm["control_token"], {
        "robot_id": "david-car", "connection_id": pair["connection_id"],
        "command_id": "move_1", "state": "rejected", "result": {"reason": "no scan"}
    })["accepted"]


def test_control_lease_expires_and_reinvite_revokes_it(tmp_path):
    now = [100.0]
    link = RemoteRoverLink(tmp_path, clock=lambda: now[0])
    pair = enroll(link)
    arm = link.arm("david-car")
    now[0] += 301
    with pytest.raises(PermissionError):
        link.poll_commands(arm["control_token"])
    link.invite("david-car")
    with pytest.raises(PermissionError):
        link.enqueue_command(arm["control_token"], {
            "robot_id": "david-car", "connection_id": pair["connection_id"],
            "command_id": "move_2", "linear_mm_s": 0, "angular_mrad_s": 0,
            "timeout_ms": 100})


def test_gateway_control_token_is_used_only_for_commands():
    from System.stigmerobotics_remote_link import RemoteRoverGateway

    calls = []
    class Response:
        def __init__(self, body):
            self.body = body
        def read(self, _size):
            return self.body
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return None
    class Opener:
        def open(self, request, timeout):
            calls.append((request.full_url, request.get_header("Authorization")))
            if request.get_method() == "GET":
                return Response(b'{"robot_id":"david-car","connection_id":"conn_1","commands":[]}')
            return Response(b'{"accepted":true,"command_id":"move_1","state":"accepted"}')

    gateway = RemoteRoverGateway(
        "https://stigmergicoin.com", token="telemetry-token",
        control_token="control-token", robot_id="david-car", connection_id="conn_1",
        opener=Opener())
    assert gateway.poll_commands()["commands"] == []
    gateway.ack_command(command_id="move_1", state="accepted", result={"sequence": 1})
    assert calls == [
        ("https://stigmergicoin.com/api/rover/commands?limit=8", "Bearer control-token"),
        ("https://stigmergicoin.com/api/rover/command/ack", "Bearer control-token"),
    ]
