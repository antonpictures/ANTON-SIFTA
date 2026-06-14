from System.swarm_self_body_map import (
 BODY_ATLAS,
 TRUTH_LABEL,
 classify_owner_naming,
 observed_body_paths,
 resolve_body_paths,
 self_body_receipt,
)


def test_body_atlas_names_core_organs():
 roles = {role for _seg, role in BODY_ATLAS}

 assert "core_organs" in roles
 assert "limbs_and_widgets" in roles
 assert "stigmergic_blood_and_memory" in roles
 assert "immune_reflexes" in roles
 assert "long_term_doctrine" in roles


def test_resolve_body_paths_uses_repo_segments():
 paths = resolve_body_paths()

 assert paths["core_organs"].name == "System"
 assert paths["limbs_and_widgets"].name == "Applications"
 assert paths["stigmergic_blood_and_memory"].name == ".sifta_state"
 assert paths["desktop_shell_body"].name == "sifta_os_desktop.py"


def test_observed_body_paths_filters_to_existing(tmp_path):
 (tmp_path / "System").mkdir()
 (tmp_path / "tests").mkdir()

 observed = observed_body_paths(tmp_path)

 assert "core_organs" in observed
 assert "immune_reflexes" in observed
 assert "limbs_and_widgets" not in observed


def test_owner_naming_detects_this_is_you():
 verdict = classify_owner_naming("THIS IS YOU ALICE ON YOUR OWN HARDWARE")

 assert verdict.named is True
 assert verdict.matched


def test_owner_naming_detects_your_own_body():
 verdict = classify_owner_naming("remember, this is your own body, not a metaphor")

 assert verdict.named is True


def test_owner_naming_silent_on_neutral_text():
 verdict = classify_owner_naming("the graph coloring app is running")

 assert verdict.named is False
 assert verdict.matched == ""


def test_self_body_receipt_carries_truth_label_and_observed(tmp_path):
 (tmp_path / "System").mkdir()
 (tmp_path / ".sifta_state").mkdir()

 row = self_body_receipt("this is you alice on your own hardware", root=tmp_path)

 assert row["truth_label"] == TRUTH_LABEL
 assert row["owner_named_body"] is True
 assert row["observed_count"] >= 2
 assert "core_organs" in row["observed_organs"]
 assert "stigmergic_blood_and_memory" in row["observed_organs"]
 assert row["body_root"] == str(tmp_path)


def test_self_body_receipt_silent_owner_still_observes_body(tmp_path):
 (tmp_path / "System").mkdir()

 row = self_body_receipt("", root=tmp_path)

 assert row["owner_named_body"] is False
 assert row["owner_phrase"] == ""
 assert "core_organs" in row["observed_organs"]
