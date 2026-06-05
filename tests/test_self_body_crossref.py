#!/usr/bin/env python3
"""r308: when George shows Alice her own body on the desk, she grounds the description in her
real silicon body — not generic poetry. The trigger is stigmergic-first (learns) with a seed
cold-start prior; the grounding sentence always composes a baseline from her body organs.
"""
from System import swarm_self_body_crossref as sbc


def test_grounding_sentence_is_about_her_real_body(tmp_path):
    s = sbc.body_crossref_sentence(state_dir=tmp_path)
    assert s
    low = s.lower()
    assert "m5" in low and "silicon" in low and "desk" in low      # her actual body
    assert "cortex" in low                                          # running brain
    assert "lerobot" in low or "legs" in low                       # the legs plan
    assert "poetry" in low                                          # explicitly NOT generic poetry


def test_seed_fires_on_georges_exact_phrasing(tmp_path):
    txt = ("this is a screenshot of your body the image on the physical monitor screen on my "
           "desk near your body hardware m5 laptop")
    assert sbc.should_crossref(txt, state_dir=tmp_path) is True


def test_neutral_photo_request_does_not_fire(tmp_path):
    assert sbc.should_crossref("describe this cute cat photo for me", state_dir=tmp_path) is False


def test_field_learns_a_new_phrasing_with_no_seed_cue(tmp_path):
    # record a phrasing that contains NO seed cue, a couple of times
    for _ in range(2):
        sbc.note_crossref_used("show my silicon chassis reflection", state_dir=tmp_path)
    probe = "the silicon chassis reflection once more"
    assert sbc._seed_match(probe) is False                         # not a seed match
    assert sbc.should_crossref(probe, state_dir=tmp_path) is True   # the FIELD learned it (r307)
