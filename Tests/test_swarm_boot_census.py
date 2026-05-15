import json

from System.swarm_boot_census import boot_census, boot_census_lines, render_boot_banner


def test_boot_census_reads_field_payload(tmp_path):
    state = tmp_path
    (state / "organ_field_vector.jsonl").write_text(
        json.dumps(
            {
                "payload": {
                    "declared_organ_count": 19,
                    "connected_organ_count": 18,
                    "dimension_count": 64,
                    "swimmer_count": 144,
                    "unknown_vector_count": 1,
                    "coupling_edge_count": 52,
                    "field_completeness": 0.947,
                }
            }
        )
        + "\n",
        encoding="utf-8",
    )

    census = boot_census(state_dir=state, probe_body=False, probe_identity=False)

    assert census["field_declared_organs"] == 19
    assert census["field_connected_organs"] == 18
    assert census["field_dimensions"] == 64
    assert census["field_swimmers"] == 144
    assert census["field_coupling_edges"] == 52
    assert census["field_completeness"] == 0.947


def test_boot_census_lines_do_not_collapse_runtime_to_one_organ_count():
    lines = boot_census_lines(
        {
            "body_real_organs": 17,
            "body_demo_organs": 0,
            "body_broken_organs": 0,
            "body_unknown_organs": 0,
            "identity_total": 35,
            "identity_present": 16,
            "field_dimensions": 53,
            "field_swimmers": 123,
            "field_coupling_edges": 46,
            "field_completeness": 1.0,
        }
    )

    text = "\n".join(lines)
    assert "17 REAL body organs" in text
    assert "35 identity probes" in text
    assert "53 field dims" in text
    assert "123 swimmers" in text


def test_render_boot_banner_includes_precise_lanes():
    banner = render_boot_banner("PRED SIFTA")

    assert "PRED SIFTA" in banner
    assert "REAL body organs" in banner
    assert "identity probes" in banner or "Body Panel live" in banner
