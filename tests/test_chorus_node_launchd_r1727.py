from __future__ import annotations

import plistlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PLIST = ROOT / "launchd" / "com.antonia.sifta.chorus_node_server_r1727.plist"
INSTALLER = ROOT / "launchd" / "install_chorus_node_server.sh"


def test_chorus_launch_agent_is_keepalive_and_production_safe() -> None:
    with PLIST.open("rb") as handle:
        config = plistlib.load(handle)

    assert config["Label"] == "com.antonia.sifta.chorus_node_server_r1727"
    assert config["RunAtLoad"] is True
    assert config["KeepAlive"] is True
    assert config["WorkingDirectory"] == str(ROOT)
    assert config["ProgramArguments"] == [
        "/usr/local/bin/python3",
        str(ROOT / "System" / "chorus_node_server.py"),
    ]
    assert config["EnvironmentVariables"]["M5_CHORUS_PORT"] == "8100"
    assert "SIFTA_WEB_CHAT_DEV_MODE" not in config["EnvironmentVariables"]


def test_chorus_launch_agent_and_installer_contain_no_credentials() -> None:
    material = (PLIST.read_text() + INSTALLER.read_text()).lower()
    for forbidden in ("tunnel token", "api_token", "credentials-file", "cf_tunnel_token"):
        assert forbidden not in material


def test_installer_refuses_to_kill_an_unrelated_port_listener() -> None:
    installer = INSTALLER.read_text()
    assert "*System/chorus_node_server.py*)" in installer
    assert "Refusing to replace unrelated listener" in installer
    assert "pkill" not in installer
