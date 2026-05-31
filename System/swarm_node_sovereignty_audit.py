#!/usr/bin/env python3
"""Node-sovereignty audit helpers.

Species code must not bake this node's private owner identity or silicon serial
into shared runtime code. The correct path is:

* owner label -> ``swarm_kernel_identity.owner_display_name()``
* silicon label -> ``swarm_kernel_identity.owner_silicon()`` or a live probe

This module scans runtime Python in ``System/`` and ``Applications/`` and
returns concrete hits for the organism doctor matrix.
"""
from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Set


@dataclass(frozen=True)
class SovereigntyHit:
    path: str
    line: int
    kind: str
    token_kind: str
    token: str
    severity: str
    excerpt: str


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _default_identity_tokens() -> tuple[list[str], list[str]]:
    owner_tokens: list[str] = []
    serial_tokens: list[str] = []
    try:
        from System.swarm_kernel_identity import owner_name, owner_silicon

        name = (owner_name() or "").strip()
        if name and name != "<unclaimed>":
            owner_tokens.append(name)
            repo_name = _repo_root().name.lower().replace("-", "_")
            owner_tokens.extend(
                part for part in name.replace("-", " ").split()
                if (
                    len(part) >= 4
                    and not part.startswith("<")
                    and part.lower() not in repo_name
                )
            )
        silicon = (owner_silicon() or "").strip()
        if silicon and silicon not in {"UNKNOWN", "UNKNOWN_SERIAL"}:
            serial_tokens.append(silicon)
    except Exception:
        pass
    return _dedupe(owner_tokens), _dedupe(serial_tokens)


def _dedupe(values: Iterable[str]) -> list[str]:
    seen: Set[str] = set()
    out: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if not text:
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(text)
    return out


def _source_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for dirname in ("System", "Applications"):
        base = root / dirname
        if not base.exists():
            continue
        for path in base.rglob("*.py"):
            rel = path.relative_to(root)
            parts = set(rel.parts)
            if "__pycache__" in parts or "dist" in parts:
                continue
            if path.name == "swarm_node_sovereignty_audit.py":
                continue
            files.append(path)
    return sorted(files)


def _docstring_constant_ids(tree: ast.AST) -> set[int]:
    ids: set[int] = set()
    for node in ast.walk(tree):
        body = getattr(node, "body", None)
        if not isinstance(body, list) or not body:
            continue
        first = body[0]
        if (
            isinstance(first, ast.Expr)
            and isinstance(first.value, ast.Constant)
            and isinstance(first.value.value, str)
        ):
            ids.add(id(first.value))
    return ids


def _match_token(text: str, owner_tokens: Sequence[str], serial_tokens: Sequence[str]) -> Optional[tuple[str, str]]:
    for token in serial_tokens:
        if token and token in text:
            return "serial", token
    lower = text.lower()
    for token in owner_tokens:
        if token and token.lower() in lower:
            return "owner", token
    return None


def scan_node_sovereignty_literals(
    *,
    root: Optional[Path | str] = None,
    owner_tokens: Optional[Sequence[str]] = None,
    serial_tokens: Optional[Sequence[str]] = None,
    max_hits: int = 200,
) -> List[SovereigntyHit]:
    """Scan runtime species code for private owner/serial literals.

    Comments and docstrings are ignored. Tests and docs are not scanned here; the
    matrix is intended to catch runtime code that can speak or act on another
    node. String literals are critical because they can leak into prompts,
    receipts, labels, or network messages. Identifiers and paths are warnings
    because they still reduce portability but often need migration shims.
    """
    repo = Path(root) if root is not None else _repo_root()
    if owner_tokens is None or serial_tokens is None:
        default_owner, default_serial = _default_identity_tokens()
        if owner_tokens is None:
            owner_tokens = default_owner
        if serial_tokens is None:
            serial_tokens = default_serial
    owners = _dedupe(owner_tokens)
    serials = _dedupe(serial_tokens)
    if not owners and not serials:
        return []

    hits: list[SovereigntyHit] = []
    for path in _source_files(repo):
        rel = str(path.relative_to(repo))
        path_match = _match_token(rel, owners, serials)
        if path_match:
            token_kind, token = path_match
            hits.append(SovereigntyHit(rel, 1, "path", token_kind, token, "WARN", rel))
        try:
            text = path.read_text(encoding="utf-8")
            tree = ast.parse(text)
        except Exception:
            continue
        doc_ids = _docstring_constant_ids(tree)
        for node in ast.walk(tree):
            if len(hits) >= max_hits:
                return hits
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                if id(node) in doc_ids:
                    continue
                match = _match_token(node.value, owners, serials)
                if match:
                    token_kind, token = match
                    excerpt = " ".join(node.value.split())[:180]
                    hits.append(
                        SovereigntyHit(
                            rel,
                            getattr(node, "lineno", 0),
                            "string",
                            token_kind,
                            token,
                            "CRITICAL",
                            excerpt,
                        )
                    )
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                match = _match_token(node.name, owners, ())
                if match:
                    token_kind, token = match
                    hits.append(
                        SovereigntyHit(
                            rel,
                            getattr(node, "lineno", 0),
                            "identifier",
                            token_kind,
                            token,
                            "WARN",
                            node.name,
                        )
                    )
            elif isinstance(node, ast.Name):
                match = _match_token(node.id, owners, ())
                if match:
                    token_kind, token = match
                    hits.append(
                        SovereigntyHit(
                            rel,
                            getattr(node, "lineno", 0),
                            "identifier",
                            token_kind,
                            token,
                            "WARN",
                            node.id,
                        )
                    )
            elif isinstance(node, ast.alias):
                match = _match_token(node.name, owners, ())
                if match:
                    token_kind, token = match
                    hits.append(
                        SovereigntyHit(
                            rel,
                            getattr(node, "lineno", 0),
                            "import",
                            token_kind,
                            token,
                            "WARN",
                            node.name,
                        )
                    )
    return hits


__all__ = ["SovereigntyHit", "scan_node_sovereignty_literals"]
