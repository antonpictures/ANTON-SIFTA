#!/usr/bin/env python3
"""Tests: structured photo understanding (SIFTA r239).

George 2026-05-31: detect humans / clothing / objects / location / environment from a photo so
it's queryable ("the green puffy leg things", "the rocks behind her"). Two ingest paths: strict
JSON from a capable eye, and a prose fallback that works on today's describes."""
import os
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from System import swarm_photo_understanding as pu

PROSE = ("BioHuman Body on desert rocks in a colorful floral bikini top, green bikini bottoms, "
         "fuzzy green leg warmers, and heels. Long dark hair, sunglasses up, standing among "
         "boulders and dry brush in harsh sunlight.")


def test_prose_fallback_builds_full_scene():
    sc = pu.parse_scene("", description_fallback=PROSE)
    assert sc["source"] == "prose_fallback"
    assert len(sc["humans"]) == 1
    garments = [c["piece"] for c in sc["humans"][0]["clothing"]]
    assert "leg warmers" in garments and "bikini bottoms" in garments and "heels" in garments
    assert any(o["class"] in ("rocks", "boulders") for o in sc["objects"])
    assert sc["location"]["setting"] == "desert" and sc["location"]["indoor_outdoor"] == "outdoor"
    assert sc["environment"]["lighting"]


def test_strict_json_path_parses_fenced():
    j = ('```json\n{"humans":[{"id":0,"pose":"standing","clothing":[{"piece":"leg warmers",'
         '"colors":["green"],"materials":["faux fur"],"zones":["legs"]}]}],'
         '"objects":[{"class":"boulder","relation":"behind"}],'
         '"location":{"setting":"desert","indoor_outdoor":"outdoor"},'
         '"environment":{"lighting":"harsh sunlight","background":["dry brush"]}}\n```')
    sc = pu.parse_scene(j)
    assert sc["source"] == "vision_arm_json"
    assert sc["humans"][0]["clothing"][0]["piece"] == "leg warmers"
    assert sc["objects"][0]["class"] == "boulder"
    assert sc["location"]["setting"] == "desert"


def test_resolver_clothing_and_object_and_location():
    sc = pu.parse_scene("", description_fallback=PROSE)
    cloth = pu.resolve_scene_query("search the green puffy leg things", sc, description=PROSE)
    assert cloth["kind"] == "clothing" and "leg warmers" in cloth["query"]
    obj = pu.resolve_scene_query("where can I get the rocks behind her", sc, description=PROSE)
    assert obj["kind"] == "object" and "rock" in obj["query"]
    loc = pu.resolve_scene_query("what is the background setting", sc, description=PROSE)
    assert loc["kind"] in ("location", "object")  # resolves to setting/background


def test_block_is_first_person_structured():
    block = pu.scene_understanding_block(pu.parse_scene("", description_fallback=PROSE))
    assert "WHAT I SEE" in block and "human" in block and "objects:" in block and "location:" in block


def test_record_and_latest_scene(tmp_path):
    state = tmp_path / ".sifta_state"
    state.mkdir()
    sc = pu.parse_scene("", description_fallback=PROSE)
    pu.record_scene("https://insta/p/x", sc, arm="ollama_vision_agent", image_hash="abc",
                    frame_epoch=1.0, state_dir=state)
    got = pu.latest_scene(url="https://insta/p/x", state_dir=state)
    assert got and got["arm"] == "ollama_vision_agent" and got["scene"]["humans"]


def test_empty_input_is_empty_scene():
    sc = pu.parse_scene("", description_fallback="")
    assert sc["humans"] == [] and sc["objects"] == []


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
