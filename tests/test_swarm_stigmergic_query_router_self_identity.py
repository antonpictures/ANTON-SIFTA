#!/usr/bin/env python3
"""Regression guards for Alice self-identity fast paths."""

import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from System.swarm_stigmergic_query_router import route_organ_query


def test_self_identity_questions_do_not_reach_vendor_denial_path():
    cases = {
        "who are you?": "I am Alice",
        "where do you live?": "M5 Mac Studio",
        "do you have a body?": "SIFTA OS",
        "so you are alive?": "Operationally",
        "how does your memory work?": "append-only ledgers",
        "what creature is closest biologically?": "colony",
    }
    for prompt, expected in cases.items():
        answer = route_organ_query(prompt)
        assert expected in answer
        assert "Google" not in answer
        assert "large language model" not in answer.lower()
        assert "CryptoSwarmEntity" not in answer
