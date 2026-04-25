from __future__ import annotations

from pathlib import Path

from scripts import distro_scrubber


def test_distro_scrubber_skips_generated_build_artifacts() -> None:
    assert distro_scrubber.should_skip_dir("build")
    assert distro_scrubber.should_skip_dir("node_modules")
    assert distro_scrubber.should_skip_file(Path("libalice.dylib"))
    assert distro_scrubber.should_skip_file(Path("compiled.o"))


def test_distro_scrubber_byte_audit_catches_binary_pii(tmp_path: Path) -> None:
    leak = tmp_path / "native_blob.bin"
    leak.write_bytes(b"\x00prefix ioanganton suffix\x00")

    leaks = distro_scrubber.hard_pii_leaks(tmp_path, distro_scrubber.get_ignore_list())

    assert leaks == [("native_blob.bin", "ioanganton", 1)]


def test_distro_scrubber_replaces_pii_in_bytes() -> None:
    data = b"GTH4921YP3:/Users/ioanganton"

    scrubbed = distro_scrubber.scrub_bytes(data)

    assert b"GTH4921YP3" not in scrubbed
    assert b"ioanganton" not in scrubbed
    assert b"<YOUR_SILICON_SERIAL>" in scrubbed
