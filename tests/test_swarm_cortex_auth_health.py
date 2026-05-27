from __future__ import annotations

import json
import time
from pathlib import Path

from System.swarm_cortex_auth_health import check_xai_oauth_health


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _append_jsonl(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row) + "\n")


def test_green_when_oauth_exists_and_no_recent_failover(tmp_path: Path) -> None:
    auth = tmp_path / "auth.json"
    _write(
        auth,
        {
            "credential_pool": {
                "xai-oauth": [
                    {"access_token": "oauth-hermes-pool-123456", "label": "default"}
                ]
            }
        },
    )

    out = check_xai_oauth_health(tmp_path, hermes_auth_path=str(auth))
    assert out["status"] == "green"
    assert out["reason"] == "oauth_present_no_recent_failover"
    assert out["last_failover_age_s"] is None


def test_red_when_xai_oauth_missing(tmp_path: Path) -> None:
    auth = tmp_path / "auth.json"
    _write(
        auth,
        {
            "providers": {
                "openai-codex": {
                    "tokens": {"access_token": "sk-test-123"}
                }
            }
        },
    )

    out = check_xai_oauth_health(tmp_path, hermes_auth_path=str(auth))
    assert out["status"] == "red"
    assert out["reason"] == "missing_xai_oauth_credential"


def test_red_when_recent_failover_exists(tmp_path: Path) -> None:
    auth = tmp_path / "auth.json"
    _write(
        auth,
        {
            "providers": {
                "xai-oauth": {
                    "tokens": {"access_token": "oauth-hermes-provider-abcdef"}
                }
            }
        },
    )
    _append_jsonl(
        tmp_path / "cortex_failover.jsonl",
        {
            "kind": "CORTEX_AUTH_FAILOVER",
            "ts": time.time() - 60.0,
        },
    )

    out = check_xai_oauth_health(tmp_path, hermes_auth_path=str(auth))
    assert out["status"] == "red"
    assert out["reason"] == "recent_cortex_auth_failover"
    assert isinstance(out["last_failover_age_s"], float)
    assert 0.0 <= float(out["last_failover_age_s"]) <= 300.0
