import importlib.util
from pathlib import Path


def _load_talk_module():
    root = Path(__file__).resolve().parents[1]
    path = root / "Applications" / "sifta_talk_to_alice_widget.py"
    spec = importlib.util.spec_from_file_location("sifta_talk_to_alice_widget_url_test", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def test_spoken_bad_domain_is_not_rewritten_to_a_different_site():
    mod = _load_talk_module()
    cmd = mod._extract_sifta_app_command(
        "a list please go to ticktough.com",
        ["Alice Browser", "Bonsai Image Studio (AI Vision)"],
    )

    assert cmd["kind"] == "browser_url"
    assert cmd["app_name"] == "Alice Browser"
    assert cmd["url"] == "https://ticktough.com"
    assert cmd["owner_text"] == "a list please go to ticktough.com"


def test_corrected_domain_phrase_is_browser_effector_not_story():
    mod = _load_talk_module()
    owner_text = (
        "i promise to help you as hard as i can. i will concentrate -- very good. "
        "but misunderstanding. i said tiktok.com"
    )

    assert mod._extract_browser_url(owner_text) == "https://tiktok.com"
    assert mod._is_direct_browser_url_effector_command(owner_text)

    cmd = mod._extract_sifta_app_command(
        owner_text,
        ["Alice Browser", "Bonsai Image Studio (AI Vision)"],
    )
    assert cmd["kind"] == "browser_url"
    assert cmd["app_name"] == "Alice Browser"
    assert cmd["url"] == "https://tiktok.com"
    assert cmd["owner_text"] == owner_text


def test_any_corrected_domain_uses_same_generic_path():
    mod = _load_talk_module()
    owner_text = "wrong site, I meant example.com"

    cmd = mod._extract_sifta_app_command(owner_text, ["Alice Browser"])
    assert cmd["kind"] == "browser_url"
    assert cmd["url"] == "https://example.com"
    assert cmd["owner_text"] == owner_text


def test_url_awareness_question_does_not_reload_page():
    mod = _load_talk_module()
    owner_text = "are you aware you are at https://www.tiktok.com/"

    assert mod._extract_browser_url(owner_text) == "https://www.tiktok.com/"
    assert not mod._is_direct_browser_url_effector_command(owner_text)
    assert mod._extract_sifta_app_command(owner_text, ["Alice Browser"]) == {}


def test_explicit_domain_handle_opens_profile_without_person_hardcode():
    mod = _load_talk_module()
    owner_text = "instagram.com @kylinmilan"

    cmd = mod._extract_sifta_app_command(owner_text, ["Alice Browser"])

    assert cmd["kind"] == "browser_url"
    assert cmd["app_name"] == "Alice Browser"
    assert cmd["url"] == "https://www.instagram.com/kylinmilan/"
    assert cmd["owner_text"] == owner_text


def test_any_instagram_handle_uses_same_generic_path():
    mod = _load_talk_module()
    owner_text = "instagram.com @anymodel123"

    cmd = mod._extract_sifta_app_command(owner_text, ["Alice Browser"])

    assert cmd["kind"] == "browser_url"
    assert cmd["url"] == "https://www.instagram.com/anymodel123/"


def test_unknown_explicit_domain_handle_uses_general_at_handle_path():
    mod = _load_talk_module()
    owner_text = "models.example.com @anymodel123"

    cmd = mod._extract_sifta_app_command(owner_text, ["Alice Browser"])

    assert cmd["kind"] == "browser_url"
    assert cmd["url"] == "https://models.example.com/@anymodel123"
    assert cmd["owner_text"] == owner_text


def test_browser_load_error_state_is_not_success():
    mod = _load_talk_module()
    state = {
        "url": "https://ticktough.com/",
        "title": "ticktough.com",
        "text_excerpt": "This site can't be reached ERR_NAME_NOT_RESOLVED",
    }

    assert mod._browser_load_error_from_state(state) == "This site can't be reached"
    assert mod._browser_load_error_from_state(
        {"url": "https://example.com", "title": "Example Domain", "text_excerpt": "Example Domain"}
    ) == ""


def test_browser_success_claim_is_repaired_when_page_state_is_error():
    mod = _load_talk_module()
    reply = (
        "**SUCCESS** The TikTok interface has been replaced. You are now viewing the official "
        "homepage. The main hero banner is displaying the latest announcements."
    )
    state = {
        "trace_id": "a7332de5-1358-44fc-a6b9-ee519919fd2d",
        "url": "https://nvidia.com/",
        "title": "nvidia.com",
        "text": (
            "This site can’t be reached\n\n"
            "nvidia.com took too long to respond.\n\n"
            "ERR_TIMED_OUT"
        ),
    }

    repaired = mod._browser_false_success_repair_for_state(
        reply,
        prior_user_text="open nvidia.com pls",
        state=state,
    )

    assert "ERR_TIMED_OUT" in repaired
    assert "https://nvidia.com/" in repaired
    assert "will not claim the page loaded" in repaired
    assert "homepage" not in repaired.lower()


def test_browser_honest_error_reply_is_not_rewritten_again():
    mod = _load_talk_module()
    reply = "I opened Alice Browser to https://nvidia.com/, but the browser receipt shows ERR_TIMED_OUT."
    state = {
        "url": "https://nvidia.com/",
        "title": "nvidia.com",
        "text": "This site can’t be reached ERR_TIMED_OUT",
    }

    assert (
        mod._browser_false_success_repair_for_state(
            reply,
            prior_user_text="open nvidia.com pls",
            state=state,
        )
        == reply
    )


def test_profile_detail_claim_without_page_receipt_is_repaired():
    mod = _load_talk_module()
    reply = (
        "**SUCCESS!** The page has loaded the profile for **@kylinmilan**.\n"
        "* **Profile Picture:** A clear photo.\n"
        "* **Bio:** travel and fashion.\n"
        "* **Stats:** 350K Followers.\n"
        "* **Recent Content:** the grid is filled with photos."
    )
    state = {
        "trace_id": "profile-state-1",
        "url": "https://www.instagram.com/kylinmilan/",
        "title": "Instagram",
        "text_excerpt": "Instagram login page",
    }

    repaired = mod._browser_profile_detail_repair_for_state(
        reply,
        prior_user_text="instagram.com @kylinmilan",
        state=state,
    )

    assert "will not invent" in repaired
    assert "@kylinmilan" in repaired
    assert "350K" not in repaired
    assert "profile-state-1" in repaired
