from __future__ import annotations

import json

from System import swarm_browser_interruption_recovery as recovery


def _state(
    *,
    url: str = "https://chatgpt.com/",
    title: str = "ChatGPT",
    text: str = "",
    buttons: list[str] | None = None,
    controls: list[dict] | None = None,
    content_hash: str = "hash-1",
) -> dict:
    return {
        "url": url,
        "title": title,
        "text_excerpt": text,
        "text_chars": len(text),
        "buttons": buttons or [],
        "visible_controls": controls or [],
        "content_hash": content_hash,
    }


def test_cookie_banner_is_recovery_receipt_not_generic_failure(tmp_path):
    page = _state(
        text="We use cookies to improve this site. Manage preferences or accept all.",
        controls=[
            {"label": "Accept all", "role": "button", "rect": {"width": 88, "height": 34}},
            {"label": "Reject all", "role": "button", "rect": {"width": 86, "height": 34}},
        ],
    )

    row = recovery.maybe_record_interruption(page, state_dir=tmp_path, now=1000.0)

    assert row["recorded"] is True
    assert row["kind"] == "cookie_consent"
    assert row["recommended_action"] == "choose_cookie_preference_then_resume"
    ledger = tmp_path / recovery.RECOVERY_LEDGER
    assert ledger.exists()
    assert json.loads(ledger.read_text().splitlines()[-1])["receipt_id"] == row["receipt_id"]


def test_login_required_needs_owner_input(tmp_path):
    page = _state(
        url="https://chat.openai.com/auth/login",
        text="Sign in to continue. Continue with Google. Email address Password.",
        controls=[{"label": "Continue with Google", "role": "button"}],
    )

    row = recovery.maybe_record_interruption(page, state_dir=tmp_path, now=1001.0)

    assert row["kind"] == "login_required"
    assert row["needs_owner_input"] is True
    assert row["recommended_action"] == "owner_login_then_resume"


def test_google_passkey_wall_is_named_auth_blocker(tmp_path):
    page = _state(
        url="https://accounts.google.com/v3/signin/challenge/pk",
        title="Welcome",
        text=(
            "Sign in with Google. Welcome iantongeorge@gmail.com. "
            "Verifying it's you... Complete sign-in using your passkey."
        ),
        controls=[{"label": "Try another way", "role": "button"}],
    )

    row = recovery.maybe_record_interruption(page, state_dir=tmp_path, now=1001.5)

    assert row["kind"] == "passkey_auth"
    assert row["needs_owner_input"] is True
    assert row["recommended_action"] == "owner_complete_passkey_or_try_another_way_then_resume"
    assert "Try another way" in json.dumps(row["candidate_controls"])


def test_captcha_blocks_and_does_not_auto_click(tmp_path):
    page = _state(
        text="Verify you are human. I'm not a robot. reCAPTCHA.",
        controls=[{"label": "I'm not a robot", "role": "checkbox"}],
    )

    row = recovery.maybe_record_interruption(page, state_dir=tmp_path, now=1002.0)

    assert row["kind"] == "captcha"
    assert row["blocked"] is True
    assert row["safe_auto_action"] is False
    assert row["needs_owner_input"] is True


def test_cloudflare_wait_is_wait_then_refresh(tmp_path):
    page = _state(
        title="Just a moment...",
        text="Checking your browser before accessing the site. Cloudflare security check.",
    )

    row = recovery.maybe_record_interruption(page, state_dir=tmp_path, now=1003.0)

    assert row["kind"] == "cloudflare_wait"
    assert row["safe_auto_action"] is True
    assert row["recommended_action"] == "wait_then_refresh_page_state"


def test_wrong_page_uses_expected_url_host(tmp_path):
    page = _state(url="https://x.com/home", text="Home timeline")

    row = recovery.maybe_record_interruption(
        page,
        expected_url="https://chatgpt.com/",
        state_dir=tmp_path,
        now=1004.0,
    )

    assert row["kind"] == "wrong_page"
    assert "chatgpt.com" in row["summary"]
    assert row["recommended_action"] == "navigate_expected_url"


def test_normal_chat_page_does_not_write_receipt(tmp_path):
    page = _state(
        text="What can I help with? Ask anything. New chat.",
        controls=[{"label": "Ask anything", "role": "textbox"}, {"label": "Send prompt", "role": "button"}],
    )

    row = recovery.maybe_record_interruption(page, state_dir=tmp_path, now=1005.0)

    assert row["recorded"] is False
    assert row["kind"] == "none"
    assert not (tmp_path / recovery.RECOVERY_LEDGER).exists()


def test_recent_duplicate_is_suppressed(tmp_path):
    page = _state(
        text="We use cookies. Accept all cookies.",
        controls=[{"label": "Accept all", "role": "button"}],
        content_hash="same-cookie-page",
    )

    first = recovery.maybe_record_interruption(page, state_dir=tmp_path, now=2000.0)
    second = recovery.maybe_record_interruption(page, state_dir=tmp_path, now=2020.0)

    assert first["recorded"] is True
    assert second["recorded"] is False
    assert second["reason"] == "duplicate_recent_interruption"
    lines = (tmp_path / recovery.RECOVERY_LEDGER).read_text().splitlines()
    assert len(lines) == 1


def test_recovery_monitor_lines_surface_latest_receipts(tmp_path):
    page = _state(
        text="Subscribe to continue reading this article.",
        controls=[{"label": "No thanks", "role": "button"}],
    )
    recovery.maybe_record_interruption(page, state_dir=tmp_path, now=3000.0)

    lines = recovery.recovery_monitor_lines(state_dir=tmp_path)

    joined = "\n".join(lines)
    assert "BROWSER INTERRUPTION RECOVERY" in joined
    assert "subscription_modal" in joined
    assert "close_or_owner_choose_path" in joined
