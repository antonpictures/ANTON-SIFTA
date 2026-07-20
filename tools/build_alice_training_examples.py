#!/usr/bin/env python3
"""Build receipt-first training examples (r1446/r1449).

Usage:
    python3 tools/build_alice_training_examples.py
    python3 tools/build_alice_training_examples.py --fixtures-only
    python3 tools/build_alice_training_examples.py --no-conversation
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from System.swarm_alice_training_examples import build_training_examples, write_training_examples


def main() -> int:
    parser = argparse.ArgumentParser(description="Build Alice receipt-first training_examples.jsonl")
    parser.add_argument("--fixtures-only", action="store_true", help="Only the six canonical fixtures")
    parser.add_argument("--no-conversation", action="store_true", help="Skip alice_conversation.jsonl pairing")
    parser.add_argument("--convo-limit", type=int, default=20, help="Max conversation-derived examples")
    parser.add_argument("--state-dir", type=str, default="", help="Override .sifta_state directory")
    args = parser.parse_args()

    examples = build_training_examples(
        include_fixtures=True,
        include_conversation=not args.no_conversation and not args.fixtures_only,
        convo_limit=max(1, int(args.convo_limit)),
        state_dir=args.state_dir or None,
    )
    receipt = write_training_examples(examples, state_dir=args.state_dir or None)
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())