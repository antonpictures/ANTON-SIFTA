#!/usr/bin/env python3
"""Tests: photo-subject identity (SIFTA r244).

George 2026-05-31: name the human in the photo from the PAGE, for ANY human, processed through
the cortex — never hardcoded. "DO NOT HARDCODE ANY SPECIFIC HUMAN NAME — CAN BE ANY BIOHUMAN BODY EXAMPLE, she is for test only." """
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from System import swarm_photo_identity as pi

IG_PAGE = "kylinmilan ✓ Follow\nkylinmilan For some reason this song fits the mood\nteoddelacruz"
IG_URL = "https://www.instagram.com/p/C8Lb8u2NbYt/"


def test_handle_only_when_no_name(tmp_path):
    sd = tmp_path / ".sifta_state"; sd.mkdir()
    r = pi.resolve_photo_identity(url=IG_URL, page_text=IG_PAGE, state_dir=sd)
    assert r["handle"] == "kylinmilan" and r["name"] == "" and r["source"] == "handle_only"


def test_owner_correction_binds_and_is_remembered(tmp_path):
    sd = tmp_path / ".sifta_state"; sd.mkdir()
    r = pi.resolve_photo_identity(url=IG_URL, page_text=IG_PAGE, owner_text="her name is BioHuman", state_dir=sd)
    assert r["name"] == "BioHuman" and r["source"] == "owner_correction" and r["confidence"] >= 0.99
    # later frame on the same handle, no correction -> remembered
    r2 = pi.resolve_photo_identity(url="https://www.instagram.com/p/OTHERPOST/", page_text=IG_PAGE, state_dir=sd)
    assert r2["name"] == "BioHuman" and r2["source"] == "remembered_owner_correction"


def test_any_human_not_hardcoded(tmp_path):
    sd = tmp_path / ".sifta_state"; sd.mkdir()
    r = pi.resolve_photo_identity(url="https://www.instagram.com/p/Z/", page_text="@another_model ✓ Follow",
                                  owner_text="that's Maria Lopez", state_dir=sd)
    assert r["name"] == "Maria Lopez" and r["handle"] == "another_model"
    # the BioHuman correction from another test's state must never leak in — fresh state, no BioHuman
    r2 = pi.resolve_photo_identity(url="https://x.com/someone", page_text="@someone", state_dir=sd)
    assert r2["name"] == "" and "kylin" not in (r2["name"] or "").lower()


def test_handle_with_separators_humanizes(tmp_path):
    sd = tmp_path / ".sifta_state"; sd.mkdir()
    r = pi.resolve_photo_identity(url="https://www.instagram.com/kylin.milan/", page_text="", state_dir=sd)
    assert r["name"] == "BioHuman Milan" and r["source"] == "handle_split"


def test_identity_block_first_person_and_named(tmp_path):
    sd = tmp_path / ".sifta_state"; sd.mkdir()
    r = pi.resolve_photo_identity(url=IG_URL, page_text=IG_PAGE, owner_text="call her BioHuman", state_dir=sd)
    block = pi.identity_block(r)
    assert "SUBJECT IDENTITY" in block and "BioHuman" in block
    assert "third-person" in block and "do not describe them as 'a young woman'" in block


def test_no_name_no_handle_is_empty():
    assert pi.identity_block({"name": "", "handle": ""}) == ""
    assert pi.resolve_photo_identity()["source"] == "none"


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
