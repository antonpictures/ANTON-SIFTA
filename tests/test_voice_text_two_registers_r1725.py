"""r1725 — Two registers, one voice (George 2026-07-20).

Text on the chat wall is Alice's long voice; the speaker is her
conversational voice. The cortex ends a reply with one 🗣-marked line —
the mouth speaks exactly that authored line, the wall prints the prose
above it, and speech can never sound cut off mid-essay.
"""

import importlib.util
import inspect
from pathlib import Path


def _load_widget_module():
    here = Path(__file__).resolve().parent.parent
    path = here / "Applications" / "sifta_talk_to_alice_widget.py"
    spec = importlib.util.spec_from_file_location("ttw", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_split_extracts_authored_voice_line_and_cleans_wall():
    mod = _load_widget_module()
    reply = (
        "Stigmergy este un mecanism de coordonare indirectă.\n"
        "Furnicile depun feromoni și mediul devine memoria colectivă.\n"
        "🗣 Pe scurt: furnicile comunică prin urme, nu prin ordine directe."
    )
    wall, voice = mod._split_authored_voice_line(reply)
    assert voice == "Pe scurt: furnicile comunică prin urme, nu prin ordine directe."
    assert "🗣" not in wall
    assert "feromoni" in wall


def test_split_without_marker_is_identity():
    mod = _load_widget_module()
    reply = "Plain reply with no marker. The voice of the swarm carries on."
    wall, voice = mod._split_authored_voice_line(reply)
    assert wall == reply
    assert voice == ""


def test_split_accepts_voice_colon_variant_but_not_prose_word():
    mod = _load_widget_module()
    wall, voice = mod._split_authored_voice_line(
        "Full detail here.\nVOICE: Short spoken line."
    )
    assert voice == "Short spoken line."
    assert wall == "Full detail here."
    # A prose line merely starting with the word "Voice" stays on the wall.
    prose = "Voice recognition improved this week.\nMore detail follows."
    wall2, voice2 = mod._split_authored_voice_line(prose)
    assert wall2 == prose
    assert voice2 == ""


def test_marker_only_reply_keeps_wall_nonempty():
    mod = _load_widget_module()
    wall, voice = mod._split_authored_voice_line("🗣 Da, sunt aici.")
    assert voice == "Da, sunt aici."
    assert wall == "Da, sunt aici."


def test_truncate_authored_skips_extractive_bite():
    mod = _load_widget_module()
    line = "First point stands. Second point stands. Third point stands."
    # Extractive path picks a middle bite; authored path keeps the whole line.
    assert mod._truncate_for_speech(line, authored=True) == line


def test_truncate_prefers_full_stop_over_spoken_ellipsis():
    mod = _load_widget_module()
    text = "A complete short sentence lands here. " + "x" * 400
    out = mod._truncate_for_speech(text, max_chars=100, authored=True)
    assert out.endswith("here.")
    assert not out.endswith("...")


def test_system_prompt_teaches_two_registers():
    mod = _load_widget_module()
    src = inspect.getsource(mod._current_system_prompt)
    assert "TWO REGISTERS, ONE VOICE" in src
    assert "🗣" in src
