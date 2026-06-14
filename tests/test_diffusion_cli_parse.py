#!/usr/bin/env python3
"""Falsifier for parse_diffusion_cli_output layout robustness.

Regression guard for the llada-8b "no decoded text" mute: the parser used to
drop ALL decoded text unless it strictly followed the ``total time:`` line, so
any CLI build that printed the text before the timing marker (or omitted it)
silenced the diffusion cortex on a clean exit 0. These cases pin the robust
behavior. Pure stdlib; no model or llama-diffusion-cli binary needed.
"""

from System.swarm_diffusion_cortex import parse_diffusion_cli_output

_LOG_HEAD = (
    "llama_model_loader: loaded meta data\n"
    "load_tensors: offloaded 99 layers\n"
    "ggml_metal_init: allocating\n"
    "diffusion step: 64/64\n"
    "print_info: file size = 4.4 GiB\n"
)
_PERF_TAIL = "real 3.20s\nuser 2.90s\nsys 0.30s\n"


def test_text_after_total_time_historical_layout():
    out = _LOG_HEAD + "total time: 3200.00 ms\n" + "The cortex is awake.\n" + _PERF_TAIL
    assert parse_diffusion_cli_output(out, "") == "The cortex is awake."


def test_text_before_total_time_is_recovered():
    # The exact layout that produced "no decoded text": text precedes the marker.
    out = _LOG_HEAD + "The cortex is awake.\n" + "total time: 3200.00 ms\n" + _PERF_TAIL
    assert parse_diffusion_cli_output(out, "") == "The cortex is awake."


def test_text_with_no_total_time_marker():
    out = _LOG_HEAD + "The cortex is awake.\n"
    assert parse_diffusion_cli_output(out, "") == "The cortex is awake."


def test_only_logs_and_perf_returns_empty():
    out = _LOG_HEAD + "total time: 10.0 ms\n" + _PERF_TAIL
    assert parse_diffusion_cli_output(out, "") == ""


def test_empty_returns_empty():
    assert parse_diffusion_cli_output("", "") == ""


def test_last_text_line_wins_after_marker():
    out = _LOG_HEAD + "total time: 1.0 ms\n" + "first line\n" + "final line\n"
    assert parse_diffusion_cli_output(out, "") == "final line"


def test_text_split_across_stdout_stderr():
    # llama.cpp prints logs to stderr, decoded text to stdout.
    assert parse_diffusion_cli_output("Decoded reply.\n", _LOG_HEAD) == "Decoded reply."


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"OK {name}")
    print("All diffusion CLI parse tests passed.")
