#!/usr/bin/env python3
"""
Package SIFTA skills for community submission and trade.

Input skills can be flat `skills/*.md` or community-style `skills/<name>/SKILL.md`.
Output is always community-style:

    exports/skill_submissions/<skill>/SKILL.md
    exports/skill_submissions/<skill>/skill_trade_offer_v1.json

No Tier 3 scripts are executed. Optional resources are copied only when they
already exist beside a community-style skill.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import time
import uuid
from pathlib import Path
from typing import Any

from System.swarm_skill_library import _parse_skill_markdown, build_skill_index
from System.swarm_skill_validator import validate_skill_file

_REPO = Path(__file__).resolve().parent.parent
_SKILLS_DIR = _REPO / "skills"
_EXPORT_ROOT = _REPO / "exports" / "skill_submissions"
_TRACE = _REPO / ".sifta_state" / "ide_stigmergic_trace.jsonl"
_SUBMISSION_RECEIPTS = _REPO / ".sifta_state" / "skill_submission_receipts.jsonl"


def _latest_trace_id() -> str:
    if not _TRACE.exists():
        return "UNKNOWN_TRACE"
    for line in reversed(_TRACE.read_text(encoding="utf-8", errors="replace").splitlines()):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except Exception:
            continue
        trace_id = row.get("trace_id")
        if trace_id:
            return str(trace_id)
    return "UNKNOWN_TRACE"


def _yaml_value(value: Any) -> str:
    if isinstance(value, list):
        return "[" + ", ".join(str(v) for v in value) + "]"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, bool):
        return "true" if value else "false"
    return json.dumps(str(value), ensure_ascii=False)


def _render_frontmatter(meta: dict[str, Any]) -> str:
    lines = ["---"]
    for key in sorted(meta):
        lines.append(f"{key}: {_yaml_value(meta[key])}")
    lines.append("---")
    return "\n".join(lines) + "\n"


def _display_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(_REPO).as_posix()
    except ValueError:
        return resolved.as_posix()


def _source_path_for(skill: dict[str, Any], skills_dir: Path = _SKILLS_DIR) -> Path:
    procedure = skill.get("procedure_file")
    if not procedure:
        raise ValueError(f"skill {skill.get('name')} has no procedure_file")
    return skills_dir / str(procedure)


def _copy_resources(src: Path, dst: Path) -> dict[str, int]:
    counts: dict[str, int] = {"scripts": 0, "references": 0, "assets": 0}
    if src.name != "SKILL.md":
        return counts
    for name in counts:
        root = src.parent / name
        if not root.exists():
            continue
        target = dst / name
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(root, target)
        counts[name] = sum(1 for p in target.rglob("*") if p.is_file())
    return counts


def package_skill(
    skill_name: str,
    *,
    output_root: Path = _EXPORT_ROOT,
    homeworld_serial: str = "GTH4921YP3",
    trace_id: str | None = None,
    stgm_price: float | None = None,
) -> dict[str, Any]:
    trace = trace_id or _latest_trace_id()
    skill_rows = {str(s.get("name")): s for s in build_skill_index()}
    if skill_name not in skill_rows:
        raise KeyError(f"unknown skill: {skill_name}")
    skill = skill_rows[skill_name]
    src = _source_path_for(skill)
    text = src.read_text(encoding="utf-8")
    meta, body = _parse_skill_markdown(text)
    body_sha = hashlib.sha256(body.encode("utf-8")).hexdigest()

    package_dir = output_root / skill_name
    package_dir.mkdir(parents=True, exist_ok=True)
    package_rel = _display_path(package_dir)
    package_skill_path = package_dir / "SKILL.md"

    packaged_meta = dict(meta)
    packaged_meta.update(
        {
            "homeworld_serial": homeworld_serial,
            "trace_id": trace,
            "source_path": src.relative_to(_REPO).as_posix(),
            "skill_sha256": body_sha,
            "submission_schema": "SIFTA_SKILL_SUBMISSION_V1",
            "truth_label": "SIFTA_HARDWARE_BOUND_SKILL",
        }
    )
    package_skill_path.write_text(
        _render_frontmatter(packaged_meta) + "\n" + body,
        encoding="utf-8",
    )
    resource_counts = _copy_resources(src, package_dir)

    price = float(
        stgm_price
        if stgm_price is not None
        else skill.get("stgm_mint")
        or meta.get("stgm_mint")
        or 0.0
    )
    offer = {
        "offer_id": str(uuid.uuid4()),
        "skill_name": skill_name,
        "skill_sha256": body_sha,
        "stgm_price": price,
        "provider_node": homeworld_serial,
        "provider_trace": trace,
        "package_path": package_rel,
        "truth_label": "SIFTA_SKILL_TRADE_OFFER_V1",
    }
    offer_path = package_dir / "skill_trade_offer_v1.json"
    offer_path.write_text(json.dumps(offer, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    validation_errors = validate_skill_file(package_skill_path)
    return {
        "skill_name": skill_name,
        "package_path": package_rel,
        "skill_file": _display_path(package_skill_path),
        "offer_file": _display_path(offer_path),
        "skill_sha256": body_sha,
        "resource_counts": resource_counts,
        "validation_errors": validation_errors,
        "ok": not validation_errors,
    }


def _write_submission_receipt(manifest: dict[str, Any]) -> str:
    _SUBMISSION_RECEIPTS.parent.mkdir(parents=True, exist_ok=True)
    receipt = {
        "schema": "SIFTA_SKILL_SUBMISSION_RECEIPT_V1",
        "ts": time.time(),
        "trace_id": str(uuid.uuid4()),
        "provider_trace": manifest.get("trace_id"),
        "homeworld_serial": manifest.get("homeworld_serial"),
        "package_count": len(manifest.get("packages", [])),
        "ok": bool(manifest.get("ok")),
        "packages": [
            {
                "skill_name": row.get("skill_name"),
                "skill_sha256": row.get("skill_sha256"),
                "package_path": row.get("package_path"),
            }
            for row in manifest.get("packages", [])
        ],
    }
    with _SUBMISSION_RECEIPTS.open("a", encoding="utf-8") as f:
        f.write(json.dumps(receipt, sort_keys=True) + "\n")
    return str(receipt["trace_id"])


def package_all(
    *,
    output_root: Path = _EXPORT_ROOT,
    homeworld_serial: str = "GTH4921YP3",
    trace_id: str | None = None,
    write_receipt: bool = False,
) -> dict[str, Any]:
    rows = []
    for skill in build_skill_index():
        if not skill.get("procedure_file") or not skill.get("procedure_exists"):
            continue
        rows.append(
            package_skill(
                str(skill["name"]),
                output_root=output_root,
                homeworld_serial=homeworld_serial,
                trace_id=trace_id,
            )
        )
    manifest = {
        "schema": "SIFTA_SKILL_SUBMISSION_MANIFEST_V1",
        "ts": time.time(),
        "homeworld_serial": homeworld_serial,
        "trace_id": trace_id or _latest_trace_id(),
        "packages": rows,
        "ok": all(r["ok"] for r in rows),
        "resource_policy": "NO_TIER3_EXECUTION_DURING_PACKAGING",
    }
    output_root.mkdir(parents=True, exist_ok=True)
    if write_receipt:
        manifest["receipt_trace_id"] = _write_submission_receipt(manifest)
    (output_root / "submission_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("skill", nargs="?", help="Skill name to package. Omit for all skills.")
    parser.add_argument("--output", default=str(_EXPORT_ROOT))
    parser.add_argument("--homeworld-serial", default="GTH4921YP3")
    parser.add_argument("--trace-id", default=None)
    args = parser.parse_args()

    output = Path(args.output)
    if args.skill:
        result = package_skill(
            args.skill,
            output_root=output,
            homeworld_serial=args.homeworld_serial,
            trace_id=args.trace_id,
        )
    else:
        result = package_all(
            output_root=output,
            homeworld_serial=args.homeworld_serial,
            trace_id=args.trace_id,
            write_receipt=True,
        )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result.get("ok", False) else 1


if __name__ == "__main__":
    raise SystemExit(main())
