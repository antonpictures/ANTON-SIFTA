"""Unit tests for LTO archive demo helpers (no Qt required)."""
from Applications.sifta_lto_archive_demo_widget import cartridges_needed, compressed_tb


def test_compressed_tb_marketing_ratio() -> None:
    assert compressed_tb(30.0) == 75.0
    assert compressed_tb(40.0) == 100.0


def test_cartridges_needed_ceil() -> None:
    assert cartridges_needed(1.0, 30.0) == 1
    assert cartridges_needed(30.0, 30.0) == 1
    assert cartridges_needed(30.01, 30.0) == 2
    assert cartridges_needed(0.0, 30.0) == 0
