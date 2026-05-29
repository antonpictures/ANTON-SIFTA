from pathlib import Path


def test_talk_widget_wires_pheromone_freshness_prompt_and_timer():
    source = Path("Applications/sifta_talk_to_alice_widget.py").read_text(
        encoding="utf-8",
        errors="replace",
    )

    assert "swarm_pheromone_freshness_loop" in source
    assert "_pheromone_freshness_summary(_state_root())" in source
    assert "self.make_timer(60000, self._pheromone_freshness_tick)" in source
    assert "def _pheromone_freshness_tick" in source
    assert "write_freshness_tick(_state_root())" in source


def test_talk_widget_wires_body_writer_tick_prompt_and_adaptive_timer():
    source = Path("Applications/sifta_talk_to_alice_widget.py").read_text(
        encoding="utf-8",
        errors="replace",
    )

    assert "swarm_body_writer_tick" in source
    assert "_body_writer_tick_summary(_state_root())" in source
    assert "self._body_writer_tick_timer = QTimer(self)" in source
    assert "self._body_writer_tick_timer.setSingleShot(True)" in source
    assert "self._schedule_body_writer_tick(initial=True)" in source
    assert "def _body_writer_tick_delay_ms" in source
    assert "def _body_writer_tick" in source
    assert "tick_writer_organs(state_dir=_state_root())" in source
