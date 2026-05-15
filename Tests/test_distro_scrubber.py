from __future__ import annotations

from pathlib import Path

from scripts import distro_scrubber


def test_distro_scrubber_skips_generated_build_artifacts() -> None:
    assert distro_scrubber.should_skip_dir("build")
    assert distro_scrubber.should_skip_dir("node_modules")
    assert distro_scrubber.should_skip_dir("surgery")
    assert distro_scrubber.should_skip_dir("stigauth")
    assert distro_scrubber.should_skip_file(Path("libalice.dylib"))
    assert distro_scrubber.should_skip_file(Path("compiled.o"))
    assert distro_scrubber.should_skip_file(Path("repair_log.jsonl"))
    assert not distro_scrubber.should_skip_file(Path("Applications/apps_manifest.json"))
    assert not distro_scrubber.should_skip_file(Path("Documents/lesson_pack_v0.json"))


def test_distro_scrubber_skips_root_only_scratch_files() -> None:
    assert distro_scrubber.should_skip_root_file(Path("scratch_patch.py"))
    assert distro_scrubber.should_skip_root_file(Path("patch_ecology.py"))
    assert distro_scrubber.should_skip_root_file(Path("fix_import.py"))
    assert not distro_scrubber.should_skip_file(Path("tests/test_apps_manifest_contract.py"))


def test_distro_scrubber_byte_audit_catches_binary_pii(tmp_path: Path) -> None:
    leak = tmp_path / "native_blob.bin"
    username = "io" + "anganton"
    leak.write_bytes(b"\x00prefix " + username.encode("utf-8") + b" suffix\x00")

    leaks = distro_scrubber.hard_pii_leaks(tmp_path, distro_scrubber.get_ignore_list())

    assert leaks == [("native_blob.bin", username, 1)]


def test_distro_scrubber_replaces_pii_in_bytes() -> None:
    serial = b"GTH" + b"4921YP3"
    username = b"io" + b"anganton"
    data = serial + b":/Users/" + username

    scrubbed = distro_scrubber.scrub_bytes(data)

    assert serial not in scrubbed
    assert username not in scrubbed
    assert b"<YOUR_SILICON_SERIAL>" in scrubbed
