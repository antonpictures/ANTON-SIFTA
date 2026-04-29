import sys
from pathlib import Path
from PyQt6.QtWidgets import QApplication, QPushButton

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from Applications.sifta_finance import FinanceDashboard

_app = QApplication.instance()
if _app is None:
    _app = QApplication(sys.argv)

def test_finance_dashboard_initialization():
    """Ensure the Finance Dashboard instantiates properly and tabs are wired."""
    widget = FinanceDashboard()
    
    assert widget.tabs is not None
    assert widget.tabs.count() == 3
    assert widget.portfolio_tab is not None
    assert widget.market_tab is not None
    assert widget.warren_tab is not None
    assert widget.details_loaded is False
    assert widget.more_data_btn.text() == "More Financial Data"


def test_finance_dashboard_loads_basics_before_agent_details(monkeypatch):
    """Startup must show canonical basics without walking the heavy agent stream."""
    from Applications import sifta_finance as finance

    def fail_load_agents():
        raise AssertionError("load_agents should wait for More Financial Data")

    monkeypatch.setattr(finance, "load_agents", fail_load_agents)
    monkeypatch.setattr(
        finance,
        "finance_truth_snapshot",
        lambda: {
            "canonical_wallet_sum": 12.5,
            "minted": 20.0,
            "spend": 7.5,
            "net_supply": 12.5,
            "memory_rewards_reputation": 3.0,
            "casino_play_tokens": 0.0,
            "warnings": [],
            "metabolic": {
                "mode": "GREEN_GROW",
                "pressure": 0.0,
                "budget_multiplier": 1.0,
                "recommendation": "unit test",
            },
        },
    )

    widget = finance.FinanceDashboard()

    assert widget.details_loaded is False
    assert widget.details_status_lbl.text() == "Basics loaded first · expanded stream paused"


def test_lazy_market_and_warren_tabs_replace_placeholders(monkeypatch):
    """Pulling lazy tabs should swap placeholders without leaving stale children."""
    from Applications import sifta_finance as finance

    monkeypatch.setattr(finance.MarketplaceTab, "load_market", lambda self: None)
    monkeypatch.setattr(finance.FinanceDashboard, "_refresh_warren", lambda self: None)

    widget = finance.FinanceDashboard()

    assert widget.tabs.tabText(1) == "⏳ Inference Market"
    assert widget.tabs.tabText(2) == "⏳ Warren Buffett"

    widget._pull_market_data()
    widget._pull_warren_data()

    assert widget._market_loaded is True
    assert isinstance(widget._real_market, finance.MarketplaceTab)
    assert widget.market_tab.layout().count() == 1
    assert not [
        btn for btn in widget.market_tab.findChildren(QPushButton)
        if "Pull Data" in btn.text()
    ]

    assert widget._warren_loaded is True
    assert widget.tabs.tabText(1) == "Inference Market"
    assert widget.tabs.tabText(2) == "Warren Buffett"
    assert hasattr(widget, "warren_view")
    assert not [
        btn for btn in widget.warren_tab.findChildren(QPushButton)
        if "Pull Data" in btn.text()
    ]


def test_load_agents_reads_quorum_without_mutating_state_cache(monkeypatch, tmp_path):
    """Finance may display cache drift, but opening the dashboard must not rewrite wallets."""
    from Applications import sifta_finance as finance

    state_dir = tmp_path / ".sifta_state"
    state_dir.mkdir()
    agent_file = state_dir / "WORKER.json"
    agent_file.write_text(
        '{"id":"WORKER","energy":100,"stgm_balance":999.0,"homeworld_serial":"SERIAL"}',
        encoding="utf-8",
    )

    monkeypatch.setattr(finance, "STATE_DIR", str(state_dir))
    def fail_ledger_balance(agent_id):
        raise AssertionError("load_agents should use one cached balance map")

    monkeypatch.setattr(finance, "ledger_balance", fail_ledger_balance)
    monkeypatch.setattr(finance, "_ledger_balance_map", lambda: {"WORKER": 1.25})

    agents = finance.load_agents()
    worker = next(a for a in agents if a.get("id") == "WORKER")

    assert worker["stgm_balance"] == 1.25
    assert worker["stgm_balance_file"] == 999.0
    assert worker["stgm_cache_drift"] == 997.75
    assert '"stgm_balance":999.0' in agent_file.read_text(encoding="utf-8").replace(" ", "")


def test_load_agents_uses_one_balance_map_for_multiple_agents(monkeypatch, tmp_path):
    """Expanded Finance must not scan the full ledger once per agent card."""
    from Applications import sifta_finance as finance

    state_dir = tmp_path / ".sifta_state"
    state_dir.mkdir()
    for name in ("A", "B", "C"):
        (state_dir / f"{name}.json").write_text(
            json_for_agent(name, serial="SERIAL"),
            encoding="utf-8",
        )

    calls = {"map": 0, "ledger": 0}

    def balance_map():
        calls["map"] += 1
        return {"A": 1.0, "B": 2.0, "C": 3.0}

    def ledger_balance(agent_id):
        calls["ledger"] += 1
        raise AssertionError("per-agent ledger_balance call reintroduces UI freeze")

    monkeypatch.setattr(finance, "STATE_DIR", str(state_dir))
    monkeypatch.setattr(finance, "_ledger_balance_map", balance_map)
    monkeypatch.setattr(finance, "ledger_balance", ledger_balance)

    agents = finance.load_agents()

    assert calls == {"map": 1, "ledger": 0}
    assert [a["stgm_balance"] for a in agents[:3]] == [3.0, 2.0, 1.0]


def test_ledger_balance_map_matches_canonical_scan(monkeypatch, tmp_path):
    """The balance map should be produced by one canonical ledger pass."""
    from Applications import sifta_finance as finance
    from System import stgm_economy

    state_dir = tmp_path / ".sifta_state"
    state_dir.mkdir()
    for name in ("A", "B"):
        (state_dir / f"{name}.json").write_text(
            json_for_agent(name, serial="SERIAL"),
            encoding="utf-8",
        )
    repair_log = tmp_path / "repair_log.jsonl"
    repair_log.write_text(
        "\n".join(
            [
                '{"tx_type":"STGM_MINT","agent_id":"A","amount":5.0}',
                '{"tx_type":"STGM_SPEND","agent_id":"A","amount":2.0}',
                '{"event":"MINING_REWARD","miner_id":"B","amount_stgm":7.0}',
                '{"event":"INFERENCE_BORROW","borrower_id":"B","lender_ip":"A","fee_stgm":1.0}',
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(stgm_economy, "REPAIR_LOG", repair_log)
    monkeypatch.setattr(stgm_economy, "STATE_DIR", state_dir)
    monkeypatch.setattr(stgm_economy, "_CACHE_LAST_SCAN", None)
    monkeypatch.setattr(stgm_economy, "_CACHE_FILES_MTIME", {})

    balances = finance._ledger_balance_map()

    assert balances == {"A": 4.0, "B": 6.0}


def json_for_agent(agent_id: str, *, serial: str) -> str:
    return (
        '{"id":"%s","energy":100,"stgm_balance":999.0,'
        '"homeworld_serial":"%s"}'
    ) % (agent_id, serial)


def test_local_spend_agent_id_comes_from_matching_serial_state(tmp_path):
    from Applications.sifta_finance import local_spend_agent_id

    state_dir = tmp_path / ".sifta_state"
    state_dir.mkdir()
    (state_dir / "jeff.json").write_text(
        '{"id":"JEFF_NODE","homeworld_serial":"JEFF_SERIAL"}',
        encoding="utf-8",
    )
    (state_dir / "alice.json").write_text(
        '{"id":"ALICE_M5","homeworld_serial":"GTH4921YP3"}',
        encoding="utf-8",
    )

    assert local_spend_agent_id("JEFF_SERIAL", str(state_dir)) == "JEFF_NODE"
    assert local_spend_agent_id("GTH4921YP3", str(state_dir)) == "ALICE_M5"
    assert local_spend_agent_id("UNKNOWN", str(state_dir)) == "LOCAL_PREDATOR"


def test_finance_truth_snapshot_uses_canonical_wallet_sum(monkeypatch):
    from Applications import sifta_finance as finance
    from System import stgm_economy

    class FakeSnapshot:
        def as_dict(self):
            return {
                "canonical_wallet_sum": 12.5,
                "net_stgm": 20.0,
                "spend": 7.5,
                "canonical_minted": 20.0,
                "inference_fee_volume": 3.0,
                "memory_reward_amount": 99.0,
                "casino_player_net_play_tokens": 42.0,
                "warnings": ["unit_test_warning"],
            }

    monkeypatch.setattr(stgm_economy, "scan_economy", lambda: FakeSnapshot())
    snap = finance.finance_truth_snapshot()

    assert snap["canonical_wallet_sum"] == 12.5
    assert snap["memory_rewards_reputation"] == 99.0
    assert snap["casino_play_tokens"] == 42.0
    assert snap["metabolic"]["stgm_balance"] == 12.5
    assert "unit_test_warning" in snap["warnings"]
