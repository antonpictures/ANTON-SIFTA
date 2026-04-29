#!/usr/bin/env python3
"""
swarm_network_membrane.py — The Semi-Permeable Cell Membrane
══════════════════════════════════════════════════════════════════════

Biology doctrine: A cell without a membrane dies. 

1. Receptor Proteins (Whitelisting): DNS/IP strict filtering.
2. Ion Channels (Sanitation): Macrophages lyse scripts and oversized payloads.
3. Active Transport (ATP): Costs STGM tokens to open the membrane.

See: Documents/IDE_BOOT_COVENANT.md (proof-bearing state).
"""
from __future__ import annotations

import json
import time
import uuid
import hashlib
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Set


DEFAULT_RECEPTORS = {
    "api.openai.com",
    "github.com",
    "raw.githubusercontent.com",
    "huggingface.co",
    "arxiv.org",
    "pubmed.ncbi.nlm.nih.gov",
    "doi.org",
}

@dataclass
class ActiveTransportReceipt:
    schema: str
    ts: float
    action_id: str
    url: str
    domain: str
    method: str
    caller_id: str
    ok: bool
    stgm_cost: float
    status: str
    bytes_transferred: int
    lysed: bool
    reason: str
    content_sha256: Optional[str] = None
    integrity: str = ""


class SwarmNetworkMembrane:
    def __init__(self, root: str = ".sifta_state", *, stgm_cost: float = 1.0, max_payload_bytes: int = 500_000):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.ledger = self.root / "membrane_transport.jsonl"
        self.receptors_file = self.root / "membrane_receptors.json"
        self.stgm_wallet = self.root / "alice_stgm_wallet.json"
        self.stgm_cost = float(stgm_cost)
        self.max_payload_bytes = int(max_payload_bytes)
        
        self._init_receptors()
        self._init_wallet()

    def _init_receptors(self):
        if not self.receptors_file.exists():
            self.receptors_file.write_text(json.dumps(list(DEFAULT_RECEPTORS), indent=2), encoding="utf-8")

    def _init_wallet(self):
        if not self.stgm_wallet.exists():
            self.stgm_wallet.write_text(json.dumps({"balance": 1000.0}, indent=2), encoding="utf-8")

    def get_receptors(self) -> Set[str]:
        try:
            return set(json.loads(self.receptors_file.read_text(encoding="utf-8")))
        except Exception:
            return DEFAULT_RECEPTORS

    def _write_json_atomic(self, path: Path, payload: Dict[str, Any]) -> None:
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        tmp.replace(path)

    def _charge_atp(self, cost: float) -> bool:
        """Active transport requires STGM (ATP)."""
        try:
            wallet = json.loads(self.stgm_wallet.read_text(encoding="utf-8"))
            if wallet.get("balance", 0.0) < cost:
                return False
            wallet["balance"] -= cost
            self._write_json_atomic(self.stgm_wallet, wallet)
            return True
        except Exception:
            return False

    def _inspect_payload(self, data: bytes) -> tuple[bool, str]:
        """
        Ion Channel Macrophage.
        Checks for token density (size) and anomalous pathogens (scripts/eval).
        """
        if len(data) > self.max_payload_bytes:
            return True, "payload_density_exceeded"
            
        content = data.decode("utf-8", errors="ignore").lower()
        pathogen_terms = ("<script", "javascript:", "eval(", "document.cookie", "onerror=")
        if any(term in content for term in pathogen_terms):
            return True, "pathogen_script_detected"
            
        return False, "clean"

    def _lyse_payload(self, data: bytes) -> bool:
        return self._inspect_payload(data)[0]

    def transport(self, url: str, *, caller_id: str = "swarm_network_membrane", action_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Opens an active transport channel to the external environment.
        """
        action_id = action_id or f"membrane_{uuid.uuid4()}"
        caller_id = (caller_id or "anonymous").strip()
        try:
            parsed = urllib.parse.urlparse(url)
            if parsed.scheme not in {"http", "https"}:
                self._record_transport(self._receipt(
                    action_id=action_id, url=url, domain="", caller_id=caller_id,
                    ok=False, status="REJECTED", bytes_transferred=0, lysed=False,
                    reason="invalid_scheme",
                ))
                return {"ok": False, "error": "invalid_scheme"}
            domain = parsed.netloc.split(":")[0].lower()
        except Exception:
            self._record_transport(self._receipt(
                action_id=action_id, url=url, domain="", caller_id=caller_id,
                ok=False, status="REJECTED", bytes_transferred=0, lysed=False,
                reason="invalid_url",
            ))
            return {"ok": False, "error": "invalid_url"}

        # 1. Receptor Binding (Whitelist)
        if domain not in self.get_receptors():
            self._record_transport(self._receipt(
                action_id=action_id, url=url, domain=domain, caller_id=caller_id,
                ok=False, status="REJECTED", bytes_transferred=0, lysed=False,
                reason="receptor_rejected",
            ))
            return {"ok": False, "error": "receptor_rejected", "domain": domain}

        # 2. Active Transport Cost (ATP / STGM)
        if not self._charge_atp(cost=self.stgm_cost):
            self._record_transport(self._receipt(
                action_id=action_id, url=url, domain=domain, caller_id=caller_id,
                ok=False, status="REJECTED", bytes_transferred=0, lysed=False,
                reason="insufficient_atp",
            ))
            return {"ok": False, "error": "insufficient_atp"}

        # 3. Perform the request
        req = urllib.request.Request(url, headers={"User-Agent": "SIFTA/7.0 Membrane"})
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                final_url = getattr(resp, "geturl", lambda: url)()
                final_domain = urllib.parse.urlparse(str(final_url)).netloc.split(":")[0].lower()
                if final_domain and final_domain != domain and final_domain not in self.get_receptors():
                    self._record_transport(self._receipt(
                        action_id=action_id, url=url, domain=domain, caller_id=caller_id,
                        ok=False, status="LYSED", bytes_transferred=0, lysed=True,
                        reason=f"redirect_receptor_escape:{final_domain}",
                    ))
                    return {"ok": False, "error": "redirect_receptor_escape", "domain": final_domain}
                data = resp.read(self.max_payload_bytes + 1)
        except Exception as e:
            self._record_transport(self._receipt(
                action_id=action_id, url=url, domain=domain, caller_id=caller_id,
                ok=False, status="FAILED", bytes_transferred=0, lysed=False,
                reason=f"network_failure: {e}",
            ))
            return {"ok": False, "error": f"network_failure: {e}"}

        # 4. Ion Channel Sanitation (Macrophage)
        lysed, lysis_reason = self._inspect_payload(data)
        if lysed:
            self._record_transport(self._receipt(
                action_id=action_id, url=url, domain=domain, caller_id=caller_id,
                ok=False, status="LYSED", bytes_transferred=len(data), lysed=True,
                reason="pathogen_detected_or_density_exceeded",
                content_sha256=hashlib.sha256(data).hexdigest(),
            ))
            return {"ok": False, "error": "payload_lysed", "reason": lysis_reason}

        # Complete
        content_sha256 = hashlib.sha256(data).hexdigest()
        self._record_transport(self._receipt(
            action_id=action_id, url=url, domain=domain, caller_id=caller_id,
            ok=True, status="SUCCESS", bytes_transferred=len(data), lysed=False,
            reason="transport_complete", content_sha256=content_sha256,
        ))
        
        return {
            "ok": True,
            "content": data.decode("utf-8", errors="replace"),
            "bytes": len(data),
            "content_sha256": content_sha256,
        }

    def _receipt(
        self,
        *,
        action_id: str,
        url: str,
        domain: str,
        caller_id: str,
        ok: bool,
        status: str,
        bytes_transferred: int,
        lysed: bool,
        reason: str,
        content_sha256: Optional[str] = None,
    ) -> ActiveTransportReceipt:
        return ActiveTransportReceipt(
            schema="SIFTA_NETWORK_MEMBRANE_RECEIPT_V1",
            ts=time.time(),
            action_id=action_id,
            url=url,
            domain=domain,
            method="GET",
            caller_id=caller_id,
            ok=ok,
            stgm_cost=self.stgm_cost if status != "REJECTED" or reason == "insufficient_atp" else 0.0,
            status=status,
            bytes_transferred=bytes_transferred,
            lysed=lysed,
            reason=reason,
            content_sha256=content_sha256,
        )

    def _record_transport(self, receipt: ActiveTransportReceipt):
        row = asdict(receipt)
        body = {k: v for k, v in row.items() if k != "integrity"}
        row["integrity"] = hashlib.sha256(
            json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        try:
            from System.jsonl_file_lock import append_line_locked
            append_line_locked(self.ledger, json.dumps(row, separators=(",", ":")) + "\n")
        except ImportError:
            with self.ledger.open("a", encoding="utf-8") as f:
                f.write(json.dumps(row, separators=(",", ":")) + "\n")
