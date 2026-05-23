import importlib.util
import json
from pathlib import Path


REPO = Path(__file__).resolve().parent.parent
POKER_PATH = REPO / "Applications" / "sifta_video_poker.py"
MANIFEST_PATH = REPO / "Applications" / "apps_manifest.json"


def _load_poker_module():
    spec = importlib.util.spec_from_file_location("sifta_video_poker_under_test", POKER_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_video_poker_is_registered_as_game():
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    entry = manifest["Stigmergic Video Poker"]
    assert entry["category"] == "Games"
    assert entry["entry_point"] == "Applications/sifta_video_poker.py"


def test_video_poker_has_no_real_casino_vault_import():
    source = POKER_PATH.read_text(encoding="utf-8")
    assert "from System.casino_vault import" not in source
    assert "CasinoVault" not in source


def test_play_money_vault_is_in_memory_only():
    poker = _load_poker_module()
    vault = poker.PlayMoneyVault(starting_balance=10.0)

    assert vault.get_play_wallet() == 10.0
    assert vault.process_bet(2.5) is True
    assert vault.get_play_wallet() == 7.5
    assert vault.casino_balance == 2.5

    vault.process_payout(1.0, reason="unit_test")
    assert vault.get_play_wallet() == 8.5
    assert vault.casino_balance == 1.5

    assert vault.process_bet(100.0) is False
    assert vault.get_play_wallet() == 8.5
