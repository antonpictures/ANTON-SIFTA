from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "Vendor" / "alice-cli" / "sdk" / "apps" / "cli"


def test_generated_wrapper_publishes_alice_bin_not_cline() -> None:
    publish_script = (CLI / "script" / "publish-npm.ts").read_text()

    assert 'const wrapperPackageName = "@anton-sifta/alice"' in publish_script
    assert '"alice-hand": "./bin/alice.cjs"' in publish_script
    assert 'cline: "./bin/cline"' not in publish_script


def test_npm_resolver_targets_anton_sifta_platform_packages() -> None:
    resolver = (CLI / "bin" / "cline").read_text()
    postinstall = (CLI / "script" / "postinstall.mjs").read_text()

    assert '"@anton-sifta/cli-" + platform + "-" + arch' in resolver
    assert '"@cline/cli-"' not in resolver
    assert "process.env.ALICE_BIN_PATH || process.env.CLINE_BIN_PATH" in resolver
    assert 'path.join(scriptDir, ".alice")' in resolver
    assert "npm install -g @anton-sifta/alice" in resolver
    assert "`@anton-sifta/cli-${platform}-${arch}`" in postinstall
    assert 'path.join(binDir, ".alice")' in postinstall


def test_alice_bin_shim_uses_npm_safe_resolver() -> None:
    shim = (CLI / "bin" / "alice.cjs").read_text()

    assert shim.startswith("#!/usr/bin/env node")
    assert 'require("./cline.cjs");' in shim
    assert "../src/index.ts" not in shim


def test_publish_script_materializes_workspace_dependencies() -> None:
    publish_script = (CLI / "script" / "publish-npm.ts").read_text()

    assert "rewriteWorkspaceRangesForNpm" in publish_script
    assert 'range.startsWith("workspace:")' in publish_script
    assert "workspaceVersions" in publish_script
