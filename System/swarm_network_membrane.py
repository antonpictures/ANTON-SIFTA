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
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, Set


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
    ts: float
    url: str
    domain: str
    stgm_cost: float
    status: str
    bytes_transferred: int
    lysed: bool
    reason: str


class SwarmNetworkMembrane:
    def __init__(self, root: str = ".sifta_state"):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.ledger = self.root / "membrane_transport.jsonl"
        self.receptors_file = self.root / "membrane_receptors.json"
        self.stgm_wallet = self.root / "alice_stgm_wallet.json"
        
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

    def _charge_atp(self, cost: float) -> bool:
        """Active transport requires STGM (ATP)."""
        try:
            wallet = json.loads(self.stgm_wallet.read_text(encoding="utf-8"))
            if wallet.get("balance", 0.0) < cost:
                return False
            wallet["balance"] -= cost
            self.stgm_wallet.write_text(json.dumps(wallet, indent=2), encoding="utf-8")
            return True
        except Exception:
            return False

    def _lyse_payload(self, data: bytes) -> bool:
        """
        Ion Channel Macrophage.
        Checks for token density (size) and anomalous pathogens (scripts/eval).
        """
        if len(data) > 500_000:  # 500KB strict density limit
            return True
            
        content = data.decode("utf-8", errors="ignore").lower()
        if "<script" in content or "eval(" in content:
            return True
            
        return False

    def transport(self, url: str) -> Dict[str, Any]:
        """
        Opens an active transport channel to the external environment.
        """
        try:
            parsed = urllib.parse.urlparse(url)
            if parsed.scheme not in {"http", "https"}:
                return {"ok": False, "error": "invalid_scheme"}
            domain = parsed.netloc.split(":")[0].lower()
        except Exception:
            return {"ok": False, "error": "invalid_url"}

        # 1. Receptor Binding (Whitelist)
        if domain not in self.get_receptors():
            return {"ok": False, "error": "receptor_rejected", "domain": domain}

        # 2. Active Transport Cost (ATP / STGM)
        if not self._charge_atp(cost=1.0):
            return {"ok": False, "error": "insufficient_atp"}

        # 3. Perform the request
        req = urllib.request.Request(url, headers={"User-Agent": "SIFTA/7.0 Membrane"})
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = resp.read()
        except Exception as e:
            self._record_transport(ActiveTransportReceipt(
                ts=time.time(), url=url, domain=domain, stgm_cost=1.0,
                status="FAILED", bytes_transferred=0, lysed=False, reason=f"network_failure: {e}"
            ))
            return {"ok": False, "error": f"network_failure: {e}"}

        # 4. Ion Channel Sanitation (Macrophage)
        if self._lyse_payload(data):
            self._record_transport(ActiveTransportReceipt(
                ts=time.time(), url=url, domain=domain, stgm_cost=1.0,
                status="LYSED", bytes_transferred=len(data), lysed=True, 
                reason="pathogen_detected_or_density_exceeded"
            ))
            return {"ok": False, "error": "payload_lysed", "reason": "pathogen_detected_or_density_exceeded"}

        # Complete
        self._record_transport(ActiveTransportReceipt(
            ts=time.time(), url=url, domain=domain, stgm_cost=1.0,
            status="SUCCESS", bytes_transferred=len(data), lysed=False, 
            reason="transport_complete"
        ))
        
        return {
            "ok": True,
            "content": data.decode("utf-8", errors="replace"),
            "bytes": len(data)
        }

    def _record_transport(self, receipt: ActiveTransportReceipt):
        try:
            from System.jsonl_file_lock import append_line_locked
            append_line_locked(self.ledger, json.dumps(asdict(receipt)) + "\n")
        except ImportError:
            with self.ledger.open("a", encoding="utf-8") as f:
                f.write(json.dumps(asdict(receipt)) + "\n")
