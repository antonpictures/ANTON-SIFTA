#!/usr/bin/env python3
"""r272: Bonsai 'Generate your desktop' — varied default prompt + generate wrapper."""
import random

from System import swarm_desktop_wallpaper as wp


def test_default_prompt_is_themed_and_varies():
    a = wp.default_prompt_for_theme("beeson_v8", rng=random.Random(1))
    b = wp.default_prompt_for_theme("beeson_v8", rng=random.Random(2))
    assert a and b and a != b  # always different
    # themed: at least one beeson mood word appears across a few draws
    draws = [wp.default_prompt_for_theme("beeson_v8", rng=random.Random(i)) for i in range(8)]
    assert any(("honeycomb" in d or "hive" in d or "ant" in d or "bee" in d or "swarm" in d)
               for d in draws)


def test_generate_uses_default_when_prompt_empty():
    seen = {}

    def fake_gen(p, *, seed, resolution):
        seen["prompt"] = p
        return {"ok": True, "out_path": "/tmp/wall.png"}

    out = wp.generate_desktop_wallpaper("", theme_id="beeson_v8", generator=fake_gen)
    assert out["ok"] is True
    assert out["path"] == "/tmp/wall.png"
    assert out["prompt"] and out["prompt"] == seen["prompt"]  # the varied default was used


def test_generate_honors_owner_prompt():
    out = wp.generate_desktop_wallpaper(
        "a calm green field", generator=lambda p, *, seed, resolution: {"ok": True, "path": "/tmp/x.png"}
    )
    assert out["prompt"] == "a calm green field"
    assert out["ok"] is True


def test_generate_never_crashes_on_backend_error():
    def boom(p, *, seed, resolution):
        raise RuntimeError("mlx missing")
    out = wp.generate_desktop_wallpaper("x", generator=boom)
    assert out["ok"] is False
    assert "mlx missing" in out["error"]
