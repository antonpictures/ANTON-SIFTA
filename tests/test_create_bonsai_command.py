from __future__ import annotations

from Applications.sifta_talk_to_alice_widget import _is_bonsai_generation_request
from System.swarm_alice_slash_commands import handle_slash_command, registered_slash_commands


def test_create_slash_command_passes_to_bonsai_effector():
    assert _is_bonsai_generation_request("/create a photo of a red robot") == "a red robot"
    assert _is_bonsai_generation_request("/create a macbookpro") == "macbookpro"


def test_create_is_registered_and_not_swallowed_by_slash_palette(tmp_path):
    commands = {row["cmd"]: row for row in registered_slash_commands()}
    assert "/create" in commands
    result = handle_slash_command(
        "/create a photo of a red robot",
        state_dir=tmp_path,
        current_cortex="krishairnd/Gemma-4-Uncensored:latest",
    )
    assert result["handled"] is False
    assert result["error"] == ""
