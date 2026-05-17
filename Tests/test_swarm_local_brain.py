#!/usr/bin/env python3
"""
tests/test_swarm_local_brain.py — Offline test for the local Ollama brain wrapper.
"""

import json
import unittest
from unittest.mock import patch, MagicMock
import sys
from pathlib import Path

# Make sure we can import the module under test
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "System"))

import swarm_local_brain


class TestSwarmLocalBrain(unittest.TestCase):

    def test_is_available_false_when_no_daemon(self):
        with patch("socket.create_connection", side_effect=Exception("no daemon")):
            self.assertFalse(swarm_local_brain.is_available())

    def test_available_models_returns_empty_when_not_available(self):
        with patch.object(swarm_local_brain, "is_available", return_value=False):
            self.assertEqual(swarm_local_brain.available_models(), [])

    def test_stream_chat_yields_token_and_done(self):
        fake_chunks = [
            b'{"message":{"content":"Hello "},"done":false}\n',
            b'{"message":{"content":"there"},"done":false}\n',
            b'{"message":{"content":"."},"done":true}\n',
        ]

        fake_response = MagicMock()
        fake_response.__enter__.return_value = fake_response
        fake_response.__iter__.return_value = iter(fake_chunks)

        with patch("urllib.request.urlopen", return_value=fake_response):
            with patch.object(swarm_local_brain, "is_available", return_value=True):
                results = list(swarm_local_brain.stream_chat("ollama:test", [{"role": "user", "content": "hi"}]))

        tokens = [p for k, p in results if k == "token"]
        done = [p for k, p in results if k == "done"]

        self.assertIn("Hello ", tokens)
        self.assertIn("there", tokens)
        self.assertTrue(any("Hello there." in d for d in done))


if __name__ == "__main__":
    unittest.main()
