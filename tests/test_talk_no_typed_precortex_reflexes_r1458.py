"""r1458: typed owner turns do not grant pre-cortex reflex permission."""
from __future__ import annotations

from pathlib import Path


SRC = Path("Applications/sifta_talk_to_alice_widget.py")


def _source() -> str:
    return SRC.read_text(encoding="utf-8")


def test_typed_turn_is_not_a_pre_cortex_reflex_escape_hatch() -> None:
    src = _source()
    forbidden = [
        "if typed_turn or chat_reflexes_enabled:",
        "if chat_reflexes_enabled or typed_turn:",
        "(typed_turn or chat_reflexes_enabled)",
        "(chat_reflexes_enabled or typed_turn)",
    ]
    for needle in forbidden:
        assert needle not in src


def test_named_owner_shortcuts_are_behind_chat_reflex_gate() -> None:
    src = _source()
    start = src.index("    def _start_brain(")
    gated_hooks = [
        "answer_ai_chat_query(",
        "answer_read_ai_chat_query(",
        "try_handle_owner_turn(text, state_dir=_state_root())",
        "answer_post_tweet_query(text, state_dir=_state_root())",
        "answer_provider_reality_audit(",
        "answer_concept_founder_query(",
        "answer_human_identity_fast_recall(",
        "answer_philippe_saleability_question(",
        "execute_camera_switch(_cam_target)",
    ]
    for hook in gated_hooks:
        idx = src.index(hook, start)
        window = src[max(start, idx - 900):idx]
        assert "if chat_reflexes_enabled:" in window

    idx = src.index("_route_direct_tool_request_for_alice(", start)
    window = src[max(start, idx - 900):idx]
    assert "elif not chat_reflexes_enabled:" in window


def test_direct_browser_effectors_require_reflex_opt_in() -> None:
    src = _source()
    start = src.index("    def _start_brain(")
    for hook in [
        "_is_direct_browser_url_effector_command(text)",
        "_extract_sifta_app_command(text)",
        "_is_contextual_browser_search_effector_request(text)",
        "_extract_explicit_engine_search_command(",
    ]:
        idx = src.index(hook, start)
        window = src[max(start, idx - 700):idx + 420]
        assert "chat_reflexes_enabled" in window


def test_browser_button_command_becomes_cortex_affordance_context() -> None:
    import Applications.sifta_talk_to_alice_widget as talk

    block = talk._browser_action_affordance_context_block(
        "good. now click the POST button. if you can't see it, respond, that needs to be coded inside my body",
        state_dir=Path("/tmp/definitely-not-sifta-state-for-test"),
    )

    assert "BROWSER ACTION AFFORDANCE PACKET" in block
    assert '"action": "click_element"' in block
    assert '"labels": ["POST"]' in block
    assert "not shortcuts" in block
    assert "BROWSER CLAIM — RECEIPT SORT" in block
    assert "DRIFT" in block
    assert "REAL" in block
    assert "do not invent" not in block.lower()


def test_concrete_browser_action_uses_fast_cortex_budget() -> None:
    import Applications.sifta_talk_to_alice_widget as talk

    text = "click the POST button"

    assert talk._owner_effector_requires_cortex_first(text) is True
    assert talk._is_fast_browser_action_cortex_turn(text) is True
    assert talk._brain_no_token_watchdog_for_owner_turn_s(text, model="mimo:mimo-cli-default") == 2.0


def test_browser_action_worker_has_compact_prompt_switch() -> None:
    src = _source()

    assert "fast_action_context_only" in src
    assert "_fast_browser_action_system_prompt(self._layering_tail)" in src
    assert "_is_fast_browser_action_cortex_turn(text)" in src


def test_browser_finger_scores_closest_visible_control() -> None:
    browser_src = Path("Applications/sifta_alice_browser_widget.py").read_text(encoding="utf-8")

    assert "wantedAliases" in browser_src
    assert "'post', 'tweet', 'publish', 'submit', 'send', 'primary'" in browser_src
    assert "stripVisualWords" in browser_src
    assert "'retry', 'reload', 'try again'" in browser_src
    assert "closest_visible_match:true" in browser_src
    assert "bestScore < 45" in browser_src


def test_browser_inventory_is_not_first_twelve_only() -> None:
    talk_src = _source()
    browser_src = Path("Applications/sifta_alice_browser_widget.py").read_text(encoding="utf-8")

    assert "raw_controls[:80]" in talk_src
    assert "visible_controls_count_in_packet" in talk_src
    assert "inv_fn(200)" in talk_src
    assert "seen[:40]" in talk_src
    assert "def list_clickable_elements_receipt(self, max_elements: int = 200)" in browser_src
    assert "isRecoveryLabel" in browser_src


def test_deictic_blue_middle_button_routes_to_browser_finger() -> None:
    import Applications.sifta_talk_to_alice_widget as talk

    cmd = talk._extract_browser_action_command(
        "A BLUE BUTTON ON YOUR BODY NOW DISPLAYED IN THE MIDDLE:) - CLICK IT"
    )

    assert cmd["kind"] == "browser_action"
    assert cmd["action"] == "click_element"
    assert cmd["deictic_visual_affordance"] == "1"
    assert "blue" in cmd["labels"][0]
    assert "middle" in cmd["labels"][0]


def test_visual_only_button_click_preserves_control_noun() -> None:
    import Applications.sifta_talk_to_alice_widget as talk

    cmd = talk._extract_browser_action_command("click the blue button")

    assert cmd["kind"] == "browser_action"
    assert cmd["action"] == "click_element"
    assert cmd["labels"] == ["blue button"]


def test_dom_options_query_routes_to_real_inventory() -> None:
    import Applications.sifta_talk_to_alice_widget as talk

    cmd = talk._extract_browser_action_command(
        "LIST ALL THE DOM OPTIONS AVAILABLE ON THE CURRENT PAGE ON YOUR BODY"
    )

    assert cmd["kind"] == "browser_action"
    assert cmd["action"] == "list_elements"


def test_fast_browser_action_filters_non_text_diffusion_cortex(monkeypatch) -> None:
    import Applications.sifta_talk_to_alice_widget as talk

    monkeypatch.setattr(
        talk,
        "_state_root",
        lambda: Path(".sifta_state"),
    )

    def fake_active_attached_model_for_cortex(_tag, *, state_dir=None):
        return "diffusion:diffusiongemma-26b"

    import System.swarm_cortex_capabilities as caps

    monkeypatch.setattr(caps, "active_attached_model_for_cortex", fake_active_attached_model_for_cortex)
    candidates = talk._fast_action_text_model_candidates(
        [
            "mimo:mimo-cli-default",
            "diffusion:diffusiongemma-26b",
            "kaelri/qwen3.5-mt:2b",
        ]
    )

    assert "mimo:mimo-cli-default" not in candidates
    assert "diffusion:diffusiongemma-26b" not in candidates
    assert "kaelri/qwen3.5-mt:2b" not in candidates
    assert candidates
    assert all(not talk._is_fast_action_non_text_model(candidate) for candidate in candidates)


def test_button_listed_named_phrase_extracts_real_target() -> None:
    import Applications.sifta_talk_to_alice_widget as talk

    cmd = talk._extract_browser_action_command(
        "CLICK THE BUTTON LISTED ON YOUR BODY NAMED \"PREMIUM\" DO YOU UNDERSTAND?"
    )

    assert cmd["kind"] == "browser_action"
    assert cmd["action"] == "click_element"
    assert cmd["labels"] == ["PREMIUM"]
    assert talk._is_fast_browser_action_cortex_turn(
        "CLICK THE BUTTON LISTED ON YOUR BODY NAMED \"PREMIUM\" DO YOU UNDERSTAND?"
    )


def test_unless_i_tell_you_to_search_google_is_not_search_command() -> None:
    import Applications.sifta_talk_to_alice_widget as talk

    text = (
        "unless i tell you to search google or you need to search google yourself "
        "to find out something you dont know, FUCK GOOGLE"
    )

    assert talk._is_search_audit_or_routing_correction(text) is True
    assert talk._extract_browser_search_command(text) == {}


def test_click_where_it_reads_visible_text_routes_to_dom_finger() -> None:
    import Applications.sifta_talk_to_alice_widget as talk

    cmd = talk._extract_browser_action_command(
        "CLICK ON YOUR ALICE BROWSER SCREEN WHERE IT READS QUEEN VICTORIA"
    )

    assert cmd["kind"] == "browser_action"
    assert cmd["action"] == "click_element"
    assert cmd["labels"] == ["QUEEN VICTORIA"]
    assert cmd["visible_text_affordance"] == "1"
    assert talk._is_fast_browser_action_cortex_turn(
        "CLICK ON YOUR ALICE BROWSER SCREEN WHERE IT READS QUEEN VICTORIA"
    )


def test_click_article_colon_uses_article_title_not_generic_noun() -> None:
    import Applications.sifta_talk_to_alice_widget as talk

    cmd = talk._extract_browser_action_command(
        "fine, click article: epoll vs. io_uring in linux"
    )

    assert cmd["kind"] == "browser_action"
    assert cmd["action"] == "click_element"
    assert cmd["labels"] == ["epoll vs. io_uring in linux"]
    assert cmd["visible_text_affordance"] == "1"


def test_title_first_click_that_page_uses_visible_title() -> None:
    import Applications.sifta_talk_to_alice_widget as talk

    cmd = talk._extract_browser_action_command(
        "Epoll vs. io_uring in Linux please, click that page"
    )

    assert cmd["kind"] == "browser_action"
    assert cmd["action"] == "click_element"
    assert cmd["labels"] == ["Epoll vs. io_uring in Linux"]
    assert cmd["visible_text_affordance"] == "1"


def test_fake_physical_click_success_is_stripped_without_receipt() -> None:
    import Applications.sifta_talk_to_alice_widget as talk

    raw = (
        "*[Physical click confirmed]* Target element 'IUT' has been successfully "
        "clicked on your body interface!\n\nContext noted: Queen Victoria."
    )

    assert talk._domain_boilerplate_rule_id(
        raw,
        prior_user_text="ON YOUR BODY, CLICK ON IUT NOW",
    ) == "lysosome/fake-system-action-no-receipt"

    cleaned = talk._strip_unreceipted_action_claims(raw)

    assert "Physical click confirmed" not in cleaned
    assert "successfully clicked" not in cleaned
    assert "Queen Victoria" in cleaned


def test_iut_typo_routes_as_deictic_it_not_literal_label() -> None:
    import Applications.sifta_talk_to_alice_widget as talk

    cmd = talk._extract_browser_action_command("ON YOUR BODY, CLICK ON IUT NOW")

    assert cmd["kind"] == "browser_action"
    assert cmd["action"] == "click_element"
    assert "IUT" not in cmd["labels"][0].upper()
    assert "BODY" not in cmd["labels"][0].upper()
    assert cmd.get("from_body_screenshot") == "1" or cmd.get("deictic_visual_affordance") == "1"


def test_type_send_typo_does_not_become_literal_senfd_button_click() -> None:
    import Applications.sifta_talk_to_alice_widget as talk

    cmd = talk._extract_browser_action_command("try again typ, hi am alice and click senfd")
    assert cmd == {}


def test_chat_rounds_on_chatgpt_does_not_become_click_element() -> None:
    import Applications.sifta_talk_to_alice_widget as talk

    cmd = talk._extract_browser_action_command("chat 10 rounds on chatgpt about Elon Musk")
    assert cmd == {}


def test_attachment_look_back_question_without_fresh_click_does_not_become_image_click() -> None:
    import Applications.sifta_talk_to_alice_widget as talk

    text = (
        "OW, DID YOU LOOK AT THE PHOTO I ATTACHED EARLIER THAT I TOLD YOU TO CLICK? "
        "WHAT IS IN THAT ATTACHMENT, LOOK AGAIN"
    )

    assert talk._extract_browser_action_command(text) == {}
    assert talk._extract_browser_search_command(text) == {}


def test_attachment_look_plus_fresh_david_muir_click_still_executes() -> None:
    import Applications.sifta_talk_to_alice_widget as talk

    cmd = talk._extract_browser_action_command(
        "look at the attachment and click on David Muir News"
    )

    assert cmd["kind"] == "browser_action"
    assert cmd["action"] == "click_element"
    assert cmd["labels"] == ["David Muir News"]


def test_execute_best_you_can_click_david_muir_news_routes_to_browser_finger() -> None:
    import Applications.sifta_talk_to_alice_widget as talk

    text = "YOU HAVE TO EXECUTE THE COMMAND THE BEST YOU CAN. JUST EXECUTE. CLICK ON DAVID MUIR NEWS"
    cmd = talk._extract_browser_action_command(text)

    assert cmd["kind"] == "browser_action"
    assert cmd["action"] == "click_element"
    assert cmd["labels"] == ["DAVID MUIR NEWS"]
    assert talk._is_fast_browser_action_cortex_turn(text)


def test_screenshot_style_quoted_button_target_survives_owner_tail() -> None:
    import Applications.sifta_talk_to_alice_widget as talk

    text = (
        'select "install candidate skill" somehow your heartbeats are behind '
        'real world time, stay in the present. not past'
    )

    cmd = talk._extract_browser_action_command(text)

    assert cmd["kind"] == "browser_action"
    assert cmd["action"] == "click_element"
    assert cmd["labels"] == ["install candidate skill"]
    assert cmd["visible_text_affordance"] == "1"


def test_sign_in_target_drops_execute_tail() -> None:
    import Applications.sifta_talk_to_alice_widget as talk

    cmd = talk._extract_browser_action_command("yes, pls click on Sign In, you have to execute")

    assert cmd["kind"] == "browser_action"
    assert cmd["action"] == "click_element"
    assert cmd["labels"] == ["Sign In"]


def test_generic_one_button_request_lists_current_controls() -> None:
    import Applications.sifta_talk_to_alice_widget as talk

    cmd = talk._extract_browser_action_command(
        "all u have to do is click one button on this page, realize you have the page open on your body"
    )

    assert cmd["kind"] == "browser_action"
    assert cmd["action"] == "list_elements"


def test_browser_finger_scores_visual_hints_from_dom_style() -> None:
    browser_src = Path("Applications/sifta_alice_browser_widget.py").read_text(encoding="utf-8")

    assert "visualHints" in browser_src
    assert "colorScore" in browser_src
    assert "positionScore" in browser_src
    assert "backgroundColor" in browser_src
