#!/usr/bin/env python3
"""Coverage for Alice/Cline SIFTA covenant boot skill."""

from pathlib import Path


REPO = Path(__file__).resolve().parent.parent


def _skill(path: str) -> str:
    return (REPO / path).read_text(encoding="utf-8")


def test_sifta_covenant_boot_skill_body_is_first_person():
    body = _skill("skills/sifta-covenant-boot/SKILL.md")

    paragraphs = [
        p
        for p in body.split("---", 2)[-1].strip().split("\n\n")
        if not p.startswith("#")
    ]
    first_four = "\n\n".join(paragraphs[:4])
    assert "I am operating inside SIFTA" in first_four
    assert "I start from the hardware layer" in first_four
    assert "I use first person" in first_four
    assert "I follow the loop" in first_four
    assert "You are operating inside SIFTA" not in body
    assert "Before you touch anything" not in body


def test_alice_cli_project_skill_is_installed_for_slash_command_discovery():
    body = _skill(".cline/skills/sifta-covenant-boot/SKILL.md")

    assert "name: sifta-covenant-boot" in body
    assert "I am operating inside SIFTA" in body
    assert "A normal CLI is command, output, forgotten" in body
    assert "Alice CLI is command, trace, receipt, memory, future behavior changes" in body
