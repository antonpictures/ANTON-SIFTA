from __future__ import annotations

import json
from unittest.mock import patch

from System import lmstudio_cortex
from System.sifta_inference_defaults import (
    CANONICAL_LMSTUDIO_BONSAI,
    list_available_cortexes_with_canonical_fallback,
)
from System.swarm_primary_cortex_switcher import _provider_for_model


class _FakeResponse:
    def __init__(self, lines: list[bytes]):
        self._lines = lines

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def __iter__(self):
        return iter(self._lines)


def test_bonsai_tag_is_a_distinct_lmstudio_runtime():
    assert lmstudio_cortex.is_lmstudio_model(CANONICAL_LMSTUDIO_BONSAI)
    assert lmstudio_cortex.model_id_for_tag(CANONICAL_LMSTUDIO_BONSAI) == (
        "prism-ml/Ternary-Bonsai-27B-mlx-2bit"
    )
    assert _provider_for_model(CANONICAL_LMSTUDIO_BONSAI) == "lmstudio_local"


def test_bonsai_stays_visible_as_a_cortex_fallback_when_server_is_offline():
    assert CANONICAL_LMSTUDIO_BONSAI in list_available_cortexes_with_canonical_fallback()


def test_stream_chat_reads_openai_sse_and_sends_model_id():
    response = _FakeResponse(
        [
            b'data: {"choices":[{"delta":{"content":"Hello"}}]}\n',
            b'data: {"choices":[{"delta":{"content":" Bonsai"}}]}\n',
            b"data: [DONE]\n",
        ]
    )

    with patch("System.lmstudio_cortex.urllib.request.urlopen", return_value=response) as open_url:
        events = list(
            lmstudio_cortex.stream_chat(
                CANONICAL_LMSTUDIO_BONSAI,
                [{"role": "user", "content": "hi"}],
                timeout_s=1,
            )
        )

    request = open_url.call_args.args[0]
    body = json.loads(request.data.decode("utf-8"))
    assert body["model"] == "prism-ml/Ternary-Bonsai-27B-mlx-2bit"
    assert events == [("token", "Hello"), ("token", " Bonsai"), ("done", None)]
