"""r910 — self-query: trigger must not fire mid-phrase; PoUW stake is not wallet."""

from System.swarm_self_query_skill import looks_like_self_query, _canonical_spendable_line


def test_george_ambient_musing_does_not_fire():
    """Verbatim from 2026-06-10 08:44 — 'how are you GOING to say' fired the
    self-query report over an unrelated stars/galaxies musing."""
    s = (
        "how much of the stars how are you going to say and then type three "
        "would be how much of the galaxies power that you want to say"
    )
    assert looks_like_self_query(s) is False


def test_real_wellbeing_asks_still_fire():
    assert looks_like_self_query("how are you?") is True
    assert looks_like_self_query("how are you doing") is True
    assert looks_like_self_query("how are you feeling today") is True
    assert looks_like_self_query("what do you need") is True
    assert looks_like_self_query("alice run a self-check") is True


def test_canonical_spendable_line_defensive():
    # Must never raise; returns "" or a labeled canonical line.
    out = _canonical_spendable_line()
    assert isinstance(out, str)
    if out:
        assert "canonical" in out and "spendable" in out


def test_doctor_commentary_about_red_organs_does_not_fire():
    """r914: George pasted Fable commentary mentioning self-query + RED organs."""
    s = (
        "Why she got confused: you pasted my commentary, not the prompt block. "
        "Inside my commentary sat the words her own self-query named four RED organs "
        "which matched the self-query trigger and hijacked the turn."
    )
    assert looks_like_self_query(s) is False
