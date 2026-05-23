from System.stigmergic_field import FieldConfig, StigmergicField, field_dashboard, nonlinear_flip_probability


def test_stigmergic_field_reads_two_timescale_correlation():
    field = StigmergicField(FieldConfig(n_bins=8, n_channels=2, threshold=1.0))

    field.deposit(2, 0, 3.0)
    field.deposit(2, 1, 1.0)

    corr = field.read_correlation(2)
    assert corr is not None
    assert corr > 0.0
    assert field.snapshot()["deposits"] == 2


def test_stigmergic_field_decay_preserves_slow_layer_more_than_fast():
    field = StigmergicField(FieldConfig(n_bins=8, n_channels=2, fast_decay=0.5, slow_decay=0.99))
    field.deposit(1, 0, 10.0)

    before_fast = field.fast_energy
    before_slow = field.slow_energy
    field.decay()

    assert field.fast_energy < before_fast
    assert field.slow_energy < before_slow
    assert field.slow_energy > field.fast_energy


def test_nonlinear_flip_probability_is_bounded():
    prob = nonlinear_flip_probability(disagreement=10.0, gradient=100.0, kappa=5.0, max_prob=0.42)

    assert prob == 0.42


def test_stigmergic_field_persists_full_state(tmp_path):
    path = tmp_path / "field.json"
    field = StigmergicField(FieldConfig(n_bins=8, n_channels=2, threshold=0.5))
    field.deposit(3, 0, 2.0)
    field.deposit(3, 1, 0.5)

    field.save(path)
    loaded = StigmergicField.load(path, fallback_config=FieldConfig(n_bins=8, n_channels=2))

    assert loaded.snapshot()["deposits"] == 2
    assert loaded.read_correlation(3) is not None
    assert loaded.energy == field.energy


def test_field_dashboard_reads_persistent_runtime_fields(tmp_path):
    attention = StigmergicField(FieldConfig(n_bins=8, n_channels=2, threshold=0.5))
    attention.deposit(1, 0, 1.0)
    attention.save(tmp_path / "app_focus_attention_field.json")

    cortex = StigmergicField(FieldConfig(n_bins=8, n_channels=2, threshold=0.5))
    cortex.deposit(2, 0, 1.0)
    cortex.save(tmp_path / "cortex_route_field.json")

    report = field_dashboard(tmp_path)

    assert "attention_gaze" in report["fields"]
    assert "cortex_router" in report["fields"]
    assert report["fields"]["attention_gaze"]["deposits"] == 1
    assert report["fields"]["cortex_router"]["deposits"] == 1
