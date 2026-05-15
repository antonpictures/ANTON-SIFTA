from pathlib import Path


REPO = Path(__file__).resolve().parent.parent


def test_tournament_briefing_docs_are_bound_to_repo_artifacts():
    territory = REPO / "Documents" / "SIFTA_TERRITORY_BENCHMARK_MAP.md"
    text = territory.read_text(encoding="utf-8")

    assert "System/swarm_skill_library.py" in text
    assert "System/sifta_vs_nvidia_differentiator.py" in text
    assert "Applications/sifta_alice_browser_widget.py" in text
    assert "Documents/IDE_BOOT_COVENANT.md" in text
    assert "Territory SLO" in text


def test_tournament_briefing_widget_lists_all_docs():
    from Applications.sifta_tournament_briefing_widget import DOCS

    rel_paths = {rel for _title, rel in DOCS}
    assert {
        "Documents/SIFTA_TERRITORY_BENCHMARK_MAP.md",
        "Documents/IBM_AGENTS_HUB_MAPPING.md",
        "Documents/CHAMATH_NARRATIVE_PACK_V1.md",
        "Documents/NVIDIA_DIFFERENTIATOR_NOTES.md",
    } <= rel_paths
    for _title, rel in DOCS:
        assert (REPO / rel).exists(), rel
