import importlib.util
from pathlib import Path


def _load_widget_module():
    here = Path(__file__).resolve().parent.parent
    path = here / "Applications" / "sifta_talk_to_alice_widget.py"
    spec = importlib.util.spec_from_file_location("ttw_diary_prompt", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_current_system_prompt_includes_episodic_diary(monkeypatch):
    mod = _load_widget_module()

    import System.swarm_episodic_diary as diary

    monkeypatch.setattr(
        diary,
        "refresh_and_format_diary_for_prompt",
        lambda hours=4, max_rows=6: (
            "EPISODIC DIARY (rolling local day-story summaries):\n"
            "- 2026-05-02T12:00/4h labels=sleep,media events=3 "
            "-- sleep loc=bedroom media=youtube_tv_loud"
        ),
    )

    prompt = mod._current_system_prompt(user_active=True, user_text="what happened while I napped?")

    assert "EPISODIC DIARY" in prompt
    assert "2026-05-02T12:00/4h" in prompt
    assert "youtube_tv_loud" in prompt
