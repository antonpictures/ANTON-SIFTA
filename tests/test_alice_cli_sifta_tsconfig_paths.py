import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SDK = ROOT / "Vendor" / "alice-cli" / "sdk"
VITEST_CONFIG = SDK / "apps" / "cli" / "vitest.config.ts"


def _paths(relative: str) -> dict:
    data = json.loads((SDK / relative).read_text(encoding="utf-8"))
    return data["compilerOptions"]["paths"]


def test_cli_tsconfig_resolves_sifta_workspace_packages() -> None:
    paths = _paths("apps/tsconfig.apps.json")

    for key in (
        "@sifta/agents",
        "@sifta/core",
        "@sifta/core/*",
        "@sifta/llms",
        "@sifta/shared",
        "@sifta/shared/*",
    ):
        assert key in paths


def test_root_tsconfig_resolves_all_sifta_package_surfaces() -> None:
    paths = _paths("tsconfig.json")

    for key in (
        "@sifta/agents",
        "@sifta/core",
        "@sifta/core/hub",
        "@sifta/core/hub/daemon-entry",
        "@sifta/core/telemetry",
        "@sifta/llms",
        "@sifta/llms/browser",
        "@sifta/sdk",
        "@sifta/shared",
        "@sifta/shared/automation",
        "@sifta/shared/browser",
        "@sifta/shared/db",
        "@sifta/shared/storage",
        "@sifta/shared/types",
    ):
        assert key in paths


def test_runtime_uses_alice_welcome_symbol_after_rename() -> None:
    runtime_dir = SDK / "apps" / "cli" / "src" / "runtime"
    runtime_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in runtime_dir.rglob("*.ts")
        if not path.name.endswith(".test.ts")
    )
    test_text = (runtime_dir / "run-agent.test.ts").read_text(encoding="utf-8")

    assert "resolveAliceWelcomeLine" in runtime_text
    assert "resolveClineWelcomeLine" not in runtime_text
    assert "resolveAliceWelcomeLine" in test_text


def test_vitest_resolves_sifta_workspace_packages() -> None:
    text = VITEST_CONFIG.read_text(encoding="utf-8")

    for alias in (
        "@sifta\\/agents",
        "@sifta\\/core",
        "@sifta\\/llms",
        "@sifta\\/shared",
    ):
        assert alias in text


def test_package_scripts_do_not_require_bunx_binary() -> None:
    package_files = [
        SDK / "package.json",
        SDK / "packages" / "core" / "package.json",
    ]

    for path in package_files:
        scripts = json.loads(path.read_text(encoding="utf-8")).get("scripts", {})
        assert "bunx" not in json.dumps(scripts)
