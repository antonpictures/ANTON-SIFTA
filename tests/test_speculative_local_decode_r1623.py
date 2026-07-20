from System.swarm_speculative_local_decode import probe_speculative_support


def test_speculative_not_claimed_enabled_without_tags():
    p = probe_speculative_support()
    assert p["enabled"] is False
    assert p["truth_label"]
