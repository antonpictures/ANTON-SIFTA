from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]


def test_installer_shell_syntax_and_help():
    for script in ("install_sifta_v9.sh", "install_beeson_v8.sh"):
        path = ROOT / "scripts" / script
        subprocess.run(["bash", "-n", str(path)], check=True)
        result = subprocess.run(["bash", str(path), "--help"], check=True,
                                capture_output=True, text=True)
        assert "--with-vendor" in result.stdout


def test_core_install_does_not_require_vendor_or_ignore_pki_failure():
    script = (ROOT / "scripts/install_beeson_v8.sh").read_text()
    assert 'WITH_VENDOR=0' in script
    assert 'git clone --recurse-submodules' not in script
    assert 'python -m System.bootstrap_pki ||' not in script
    assert script.index('bash scripts/beeson_smoke_test.sh') < script.index('SIFTA_OS_V9_INSTALL_RECEIPT')


def test_desktop_launcher_quotes_custom_location(tmp_path):
    target = tmp_path / "my Alice's directory"
    result = subprocess.run(
        ["bash", "-c", "printf '#!/bin/bash\\ncd %q || exit 1\\nexec %q\\n' \"$1\" \"$1/SIFTA OS.command\"", "test", str(target)],
        capture_output=True, text=True, check=True,
    )
    import shlex
    lines = result.stdout.splitlines()
    assert shlex.split(lines[1])[1] == str(target)
    assert shlex.split(lines[2])[1] == str(target / "SIFTA OS.command")
