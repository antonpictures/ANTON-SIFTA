import json
import sys
from types import SimpleNamespace

from System import swarm_body_writer_tick as body


def test_old_future_and_malformed_timeouts_do_not_latch(tmp_path):
    def row(ts):
        return {"ts": ts, "truth_label": body.SUPERVISOR_TRUTH_LABEL,
                "producers": [{"status": "timeout"}]}
    path = tmp_path / body.TICK_LEDGER
    path.write_text("\n".join(json.dumps(r) for r in [
        row(1), row(1001), row("bad"), row(float("nan")), [], row(999)
    ]) + "\n")
    assert body.recent_supervisor_timeout_count(tmp_path, now=1000) == 1
    assert body.recent_supervisor_timeout_count(tmp_path, now=1400) == 0


def test_bounded_tail_ignores_large_history(tmp_path):
    path = tmp_path / body.TICK_LEDGER
    row = {"ts": 999, "truth_label": body.SUPERVISOR_TRUTH_LABEL,
           "producers": [{"status": "timeout"}]}
    path.write_text("x" * 300000 + "\n" + json.dumps(row) + "\n")
    assert body.recent_supervisor_timeout_count(tmp_path, now=1000) == 1


def test_progress_records_stage_and_completion(tmp_path, monkeypatch):
    progress = tmp_path / "body_writer_progress_latest.json"

    def basal(*args, **kwargs):
        assert json.loads(progress.read_text())["stage"] == "basal_ganglia"
        return {"producer": "basal_ganglia", "status": "ok"}

    monkeypatch.setattr(body, "_tick_basal_ganglia", basal)
    monkeypatch.setitem(sys.modules, "System.swarm_kernel_process_table", SimpleNamespace(
        sys_success_credit_global=lambda *a, **kw: None,
        sys_decay_failures_global=lambda *a, **kw: None,
    ))
    result = body.tick_writer_organs(
        state_dir=tmp_path, enable_fractal_pheromone=False,
        enable_body_brain_loop=False, enable_field_slo=False,
        enable_memory_consolidation=False, enable_metabolic_homeostasis=False,
    )
    assert result["stage_seconds"]["basal_ganglia"] >= 0
    assert json.loads(progress.read_text())["stage"] == "complete"


def test_readonly_probe_has_no_progress_writes(tmp_path):
    body.tick_writer_organs(
        state_dir=tmp_path, write_receipt=False, enable_basal_ganglia=False,
        enable_fractal_pheromone=False, enable_body_brain_loop=False,
        enable_field_slo=False, enable_memory_consolidation=False,
        enable_metabolic_homeostasis=False,
    )
    assert not (tmp_path / "body_writer_progress_latest.json").exists()
