#!/usr/bin/env python3
"""
DEPRECATED — do not use for tournament or corpus export.

The canonical Stage-1 exporter is:
  System/alice_training_corpus_exporter.py

Run:
  PYTHONPATH=. python3 -m System.alice_training_corpus_exporter --help
"""

from __future__ import annotations

import sys


def main() -> None:
    sys.stderr.write(
        "deprecated: scripts/alice_training_corpus_exporter.py is retired.\n"
        "Use: PYTHONPATH=. python3 -m System.alice_training_corpus_exporter\n"
        "(canonical module System/alice_training_corpus_exporter.py)\n"
    )
    sys.exit(2)


if __name__ == "__main__":
    main()
