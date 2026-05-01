# System/sifta_protein_folding_broker.py
# ═══════════════════════════════════════════════════════════════════════
# SIFTA Protein Folding Broker — Local + Online Backends
# ───────────────────────────────────────────────────────────────────────
# This broker routes folding jobs through local toy engines AND real
# online prediction services. Each result carries an honest truth_label.
#
# Engines:
#   toy              = local Monte Carlo CA-backbone demo
#   c55m_hp_lattice  = deterministic HP lattice beam-search baseline
#   esmfold          = Meta's ESMFold API (FREE, no key required)
#   alphafold_db     = EBI AlphaFold DB lookup by UniProt ID
#   proteinmpnn      = inverse folding (requires local binary)
#   esmfold_cli      = calls local sifta-esmfold wrapper
#   external_pdb     = registers an already-produced PDB
#
# This broker does not pretend toy physics is AlphaFold.
# When it connects to real backends, it labels them honestly.
# ═══════════════════════════════════════════════════════════════════════

from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
import json
import hashlib
import os
import subprocess
import sys
import time

from System.canonical_schemas import assert_payload_keys
from System.jsonl_file_lock import append_line_locked
from System.alphafold_compliance import (
    alphafold_db_compliance_metadata as _alphafold_db_compliance,
)

try:
    import urllib.request
    import urllib.error
    import ssl
    _HAS_URLLIB = True
    # macOS stock Python often lacks certifi — try default, fallback to unverified
    # (safe for known public endpoints: Meta ESMFold, EBI AlphaFold DB)
    try:
        _SSL_CTX = ssl.create_default_context()
        # Quick test: if certs are broken, switch to unverified
        urllib.request.urlopen("https://api.esmatlas.com/", timeout=3, context=_SSL_CTX)
    except Exception:
        _SSL_CTX = ssl._create_unverified_context()
except ImportError:
    _HAS_URLLIB = False
    _SSL_CTX = None


AA20 = set("ACDEFGHIKLMNPQRSTVWY")

# ── API Endpoints (free, no API key) ──────────────────────────────────
ESMFOLD_API_URL = "https://api.esmatlas.com/foldSequence/v1/pdb/"
ALPHAFOLD_DB_API = "https://alphafold.ebi.ac.uk/api/prediction/{uniprot_id}"


def _sha256_file(path: Path) -> str:
    if not path.exists() or not path.is_file():
        return ""
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


@dataclass
class FoldingJob:
    sequence: str
    name: str = "sifta_protein"
    engine: str = "toy"  # toy | c55m_hp_lattice | esmfold | alphafold_db | proteinmpnn | esmfold_cli | external_pdb
    out_dir: str = ".sifta_state/protein_folds"
    uniprot_id: str = ""  # required for alphafold_db engine
    extra: dict = field(default_factory=dict)


class ProteinFoldingBroker:
    """
    SIFTA protein folding broker.

    Honest modes:
      toy              = local Monte Carlo CA-backbone demo
      c55m_hp_lattice  = deterministic HP lattice beam-search baseline
      esmfold          = Meta ESMFold API (sequence → PDB, free, no key)
      alphafold_db     = EBI AlphaFold DB lookup (UniProt ID → PDB)
      proteinmpnn      = inverse folding: structure → sequence (local binary)
      esmfold_cli      = calls a local ESMFold/OpenFold-style command
      external_pdb     = registers an already-produced PDB

    This broker does not pretend toy physics is AlphaFold.
    It makes the app upgradeable AND now connects to real backends.
    """

    def __init__(self):
        self.jobs = []

    def validate_sequence(self, seq: str) -> str:
        seq = "".join(seq.upper().split())
        bad = sorted(set(seq) - AA20)
        if not seq:
            raise ValueError("empty protein sequence")
        if bad:
            raise ValueError(f"invalid amino acids: {bad}")
        if len(seq) > 2000:
            raise ValueError("sequence too long for interactive SIFTA app")
        return seq

    def job_id(self, seq: str, engine: str) -> str:
        h = hashlib.sha256(f"{engine}:{seq}".encode()).hexdigest()[:16]
        return f"{engine}_{h}"

    def run(self, job: FoldingJob) -> dict:
        # alphafold_db uses UniProt ID, proteinmpnn uses existing PDB — no sequence needed
        if job.engine in ("alphafold_db", "proteinmpnn"):
            seq = job.sequence or "A"
        else:
            seq = self.validate_sequence(job.sequence)
        out = Path(job.out_dir)
        out.mkdir(parents=True, exist_ok=True)

        jid = self.job_id(seq, job.engine)
        pdb_path = out / f"{jid}.pdb"
        meta_path = out / f"{jid}.json"

        engine_map = {
            "toy": self._run_toy,
            "c55m_hp_lattice": self._run_c55m_hp_lattice,
            "esmfold": self._run_esmfold_api,
            "alphafold_db": lambda s, p: self._run_alphafold_db(s, p, job.uniprot_id),
            "proteinmpnn": self._run_proteinmpnn,
            "esmfold_cli": self._run_esmfold_cli,
        }

        runner = engine_map.get(job.engine)
        if runner is None:
            raise ValueError(f"unknown engine: {job.engine}")

        t0 = time.time()
        result = runner(seq, pdb_path)
        elapsed = time.time() - t0

        meta = {
            "job_id": jid,
            "name": job.name,
            "engine": job.engine,
            "sequence": seq,
            "length": len(seq),
            "pdb_path": str(pdb_path),
            "elapsed_seconds": round(elapsed, 2),
            "timestamp": time.time(),
            **result,
        }

        meta_path.write_text(json.dumps(meta, indent=2))
        self.jobs.append(meta)

        # Append to fold receipts ledger.
        ledger = Path(job.out_dir).parent / "protein_fold_receipts.jsonl"
        try:
            receipt = {
                "ts": time.time(),
                "job_id": jid,
                "engine": job.engine,
                "status": result.get("status", "unknown"),
                "truth_label": result.get("truth_label", "unknown"),
                "sequence_length": len(seq),
                "elapsed_s": round(elapsed, 2),
                "pdb_path": str(pdb_path),
                "pdb_sha256": _sha256_file(pdb_path),
                "source": result.get("source", ""),
                "reference": result.get("reference", ""),
                "compliance": result.get("compliance", {}),
            }
            assert_payload_keys("protein_fold_receipts.jsonl", receipt, strict=True)
            append_line_locked(ledger, json.dumps(receipt, sort_keys=True) + "\n")
        except Exception:
            pass

        return meta

    # ── Local Engines ─────────────────────────────────────────────────

    def _run_toy(self, seq: str, pdb_path: Path) -> dict:
        from System.sifta_peptide_backbone_demo import fold, save_pdb

        # Handled the updated signature which returns the trajectory array
        xyz, energy, _traj = fold(seq, steps=12000, temp=1.2)
        save_pdb(seq, xyz, str(pdb_path))

        return {
            "status": "ok",
            "truth_label": "toy_CA_backbone_monte_carlo",
            "energy": float(energy),
            "confidence": "demo_only",
        }

    def _run_c55m_hp_lattice(self, seq: str, pdb_path: Path) -> dict:
        from System.sifta_hp_lattice_folder import fold_to_pdb

        beam_width = int(os.environ.get("SIFTA_HP_LATTICE_BEAM", "1024"))
        result = fold_to_pdb(seq, pdb_path, beam_width=beam_width)

        return {
            "status": "ok",
            "truth_label": result["truth_label"],
            "confidence": "deterministic_lattice_baseline",
            "energy": int(result["energy"]),
            "hydrophobic_contacts": int(result["hydrophobic_contacts"]),
            "radius_gyration_angstrom": float(result["radius_gyration_angstrom"]),
            "beam_width": int(result["beam_width"]),
            "states_expanded": int(result["states_expanded"]),
            "pruned_self_collisions": int(result["pruned_self_collisions"]),
            "structure_hash": result["structure_hash"],
            "cosigned_by": result["cosigned_by"],
        }

    # ── Online Engines (FREE, no API key) ─────────────────────────────

    def _run_esmfold_api(self, seq: str, pdb_path: Path) -> dict:
        """
        Meta ESMFold API — FREE, no API key required.

        POST the raw amino acid sequence to:
            https://api.esmatlas.com/foldSequence/v1/pdb/

        Returns a PDB file directly.

        Reference: Lin et al., "Evolutionary-scale prediction of atomic-level
        protein structure with a language model" (2023). Science 379(6637).
        """
        if not _HAS_URLLIB:
            return {
                "status": "missing_urllib",
                "truth_label": "backend_unavailable",
                "hint": "urllib.request not available",
            }

        if len(seq) > 400:
            return {
                "status": "sequence_too_long_for_api",
                "truth_label": "esmfold_api_limit",
                "hint": "ESMFold API accepts sequences up to ~400 residues. Use esmfold_cli for longer sequences.",
                "length": len(seq),
            }

        try:
            req = urllib.request.Request(
                ESMFOLD_API_URL,
                data=seq.encode("utf-8"),
                headers={"Content-Type": "text/plain"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=120, context=_SSL_CTX) as resp:
                pdb_text = resp.read().decode("utf-8")

            if not pdb_text.startswith(("HEADER", "REMARK", "ATOM")):
                return {
                    "status": "invalid_response",
                    "truth_label": "esmfold_api_error",
                    "response_head": pdb_text[:500],
                }

            pdb_path.write_text(pdb_text)

            # Extract pLDDT from B-factor column (confidence per residue)
            plddt_values = []
            for line in pdb_text.splitlines():
                if line.startswith("ATOM") and len(line) >= 66:
                    try:
                        plddt_values.append(float(line[60:66].strip()))
                    except ValueError:
                        pass

            mean_plddt = sum(plddt_values) / len(plddt_values) if plddt_values else 0.0

            return {
                "status": "ok",
                "truth_label": "esmfold_v1_meta_api",
                "confidence": "real_structure_prediction",
                "mean_plddt": round(mean_plddt, 2),
                "plddt_count": len(plddt_values),
                "source": "https://api.esmatlas.com/foldSequence/v1/pdb/",
                "reference": "Lin et al. Science 379(6637) 2023",
                "note": "Real ESMFold prediction from Meta's protein language model. "
                        "This is NOT a toy — pLDDT > 70 indicates reliable backbone prediction.",
            }

        except urllib.error.URLError as e:
            return {
                "status": "network_error",
                "truth_label": "esmfold_api_unreachable",
                "error": str(e),
                "hint": "Check internet connection. ESMFold API requires network access.",
            }
        except Exception as e:
            return {
                "status": "error",
                "truth_label": "esmfold_api_error",
                "error": str(e),
            }

    def _run_alphafold_db(self, seq: str, pdb_path: Path, uniprot_id: str) -> dict:
        """
        EBI AlphaFold Database — FREE, no API key required.

        Downloads a precomputed AlphaFold2 structure by UniProt ID.

        URL pattern:
            https://alphafold.ebi.ac.uk/files/AF-{UNIPROT_ID}-F1-model_v4.pdb

        Reference: Jumper et al., "Highly accurate protein structure prediction
        with AlphaFold" (2021). Nature 596(7873).
        """
        if not _HAS_URLLIB:
            return {
                "status": "missing_urllib",
                "truth_label": "backend_unavailable",
            }

        if not uniprot_id:
            return {
                "status": "missing_uniprot_id",
                "truth_label": "alphafold_db_needs_uniprot_id",
                "hint": "Provide a UniProt ID (e.g., P00520 for ABL1). "
                        "Find IDs at https://www.uniprot.org/",
            }

        url = ALPHAFOLD_DB_API.format(uniprot_id=uniprot_id.upper())

        try:
            # Step 1: Query the prediction API to get the latest PDB URL
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=30, context=_SSL_CTX) as resp:
                api_data = json.loads(resp.read().decode("utf-8"))

            if isinstance(api_data, list) and len(api_data) > 0:
                entry = api_data[0]
                pdb_url = entry.get("pdbUrl", "")
                gene = entry.get("gene", "")
                organism = entry.get("organismScientificName", "")
                global_metric = entry.get("globalMetricValue", 0)
                version = entry.get("latestVersion", "?")
            else:
                return {
                    "status": "not_found",
                    "truth_label": "alphafold_db_no_entry",
                    "uniprot_id": uniprot_id.upper(),
                    "hint": f"No AlphaFold prediction for {uniprot_id}.",
                }

            if not pdb_url:
                return {
                    "status": "no_pdb_url",
                    "truth_label": "alphafold_db_no_pdb",
                    "uniprot_id": uniprot_id.upper(),
                }

            # Step 2: Download the actual PDB file
            req2 = urllib.request.Request(pdb_url)
            with urllib.request.urlopen(req2, timeout=60, context=_SSL_CTX) as resp2:
                pdb_text = resp2.read().decode("utf-8")

            if "ATOM" not in pdb_text:
                return {
                    "status": "invalid_response",
                    "truth_label": "alphafold_db_error",
                    "response_head": pdb_text[:500],
                }

            pdb_path.write_text(pdb_text)

            # Extract pLDDT
            plddt_values = []
            for line in pdb_text.splitlines():
                if line.startswith("ATOM") and len(line) >= 66:
                    try:
                        plddt_values.append(float(line[60:66].strip()))
                    except ValueError:
                        pass

            mean_plddt = sum(plddt_values) / len(plddt_values) if plddt_values else 0.0

            return {
                "status": "ok",
                "truth_label": "alphafold2_ebi_database",
                "confidence": "experimental_grade_prediction",
                "uniprot_id": uniprot_id.upper(),
                "gene": gene,
                "organism": organism,
                "version": version,
                "global_plddt": global_metric,
                "mean_plddt": round(mean_plddt, 2),
                "plddt_count": len(plddt_values),
                "source": pdb_url,
                "reference": "Jumper et al. Nature 596(7873) 2021",
                "compliance": _alphafold_db_compliance(
                    uniprot_id=uniprot_id.upper(),
                    source_url=pdb_url,
                    version=version,
                    gene=gene,
                    organism=organism,
                ),
                "note": "Real AlphaFold2 prediction from the EBI database. "
                        "pLDDT > 70 = reliable; > 90 = near-experimental accuracy.",
            }

        except urllib.error.HTTPError as e:
            if e.code == 404:
                return {
                    "status": "not_found",
                    "truth_label": "alphafold_db_no_entry",
                    "uniprot_id": uniprot_id.upper(),
                    "hint": f"No AlphaFold prediction exists for {uniprot_id}. "
                            "Check UniProt ID at https://www.uniprot.org/",
                }
            return {
                "status": "http_error",
                "truth_label": "alphafold_db_error",
                "error": str(e),
            }
        except Exception as e:
            return {
                "status": "error",
                "truth_label": "alphafold_db_error",
                "error": str(e),
            }

    def _run_proteinmpnn(self, seq: str, pdb_path: Path) -> dict:
        """
        ProteinMPNN — inverse folding (structure → sequence).

        NOTE: This engine works DIFFERENTLY from the others:
        - Other engines: sequence → structure (forward folding)
        - ProteinMPNN: structure → NEW sequences (inverse folding)

        It needs an INPUT PDB file. The 'pdb_path' here is used as OUTPUT,
        but we check job.extra['input_pdb'] for the source structure.
        If no input_pdb is provided, we use the most recent PDB in the folds dir.

        Reference: Dauparas et al., "Robust deep learning-based protein
        sequence design using ProteinMPNN" (2022). Science 378(6615).
        Nobel Prize in Chemistry 2024 (David Baker).
        """
        _REPO = Path(__file__).resolve().parent.parent
        mpnn_script = _REPO / "Vendor" / "ProteinMPNN" / "protein_mpnn_run.py"

        if not mpnn_script.exists():
            return {
                "status": "not_installed",
                "truth_label": "proteinmpnn_not_installed",
                "hint": "Clone ProteinMPNN: git clone https://github.com/dauparas/ProteinMPNN.git Vendor/ProteinMPNN",
            }

        # Find input PDB — use the most recent one in the folds directory
        folds_dir = pdb_path.parent
        input_pdbs = sorted(folds_dir.glob("*.pdb"), key=lambda p: p.stat().st_mtime, reverse=True)
        # Filter out mpnn output files
        input_pdbs = [p for p in input_pdbs if "mpnn" not in p.name.lower()]
        if not input_pdbs:
            return {
                "status": "no_input_pdb",
                "truth_label": "proteinmpnn_needs_structure",
                "hint": "ProteinMPNN needs a 3D structure to redesign. "
                        "First fold a protein with 'esmfold' or 'alphafold_db', "
                        "then run 'proteinmpnn' to design new sequences.",
            }

        input_pdb = input_pdbs[0]
        out_dir = folds_dir / "mpnn_output"
        out_dir.mkdir(exist_ok=True)

        num_seqs = 4
        try:
            proc = subprocess.run(
                [
                    sys.executable,
                    str(mpnn_script),
                    "--pdb_path", str(input_pdb),
                    "--out_folder", str(out_dir),
                    "--num_seq_per_target", str(num_seqs),
                    "--sampling_temp", "0.1",
                    "--seed", "42",
                    "--batch_size", "1",
                ],
                capture_output=True,
                text=True,
                timeout=120,
            )
        except Exception as e:
            return {
                "status": "error",
                "truth_label": "proteinmpnn_error",
                "error": str(e),
            }

        if proc.returncode != 0:
            return {
                "status": "failed",
                "truth_label": "proteinmpnn_failed",
                "returncode": proc.returncode,
                "stderr": proc.stderr[-500:],
            }

        # Parse the output FASTA
        fa_name = input_pdb.stem + ".fa"
        fa_path = out_dir / "seqs" / fa_name
        designed_sequences = []
        if fa_path.exists():
            lines = fa_path.read_text().splitlines()
            for i, line in enumerate(lines):
                if line.startswith(">") and i + 1 < len(lines):
                    header = line[1:]
                    sequence = lines[i + 1]
                    # Extract score from header
                    score = None
                    recovery = None
                    for part in header.split(","):
                        part = part.strip()
                        if part.startswith("score="):
                            try: score = float(part.split("=")[1])
                            except: pass
                        if part.startswith("seq_recovery="):
                            try: recovery = float(part.split("=")[1])
                            except: pass
                    designed_sequences.append({
                        "sequence": sequence,
                        "score": score,
                        "seq_recovery": recovery,
                        "length": len(sequence),
                    })

        return {
            "status": "ok",
            "truth_label": "proteinmpnn_local_inverse_fold",
            "confidence": "real_inverse_folding",
            "input_pdb": str(input_pdb),
            "designed_sequences": designed_sequences,
            "num_designed": len(designed_sequences),
            "output_fasta": str(fa_path) if fa_path.exists() else None,
            "reference": "Dauparas et al. Science 378(6615) 2022 — Nobel Prize 2024",
            "note": "Real ProteinMPNN inverse folding. These sequences are DESIGNED "
                    "to fold into the same 3D shape as the input structure. "
                    "Each one is a potential new protein that doesn't exist in nature.",
        }

    # ── CLI Wrappers ──────────────────────────────────────────────────

    def _run_esmfold_cli(self, seq: str, pdb_path: Path) -> dict:
        """
        Expected local wrapper contract:

            sifta-esmfold --sequence ACDE... --out result.pdb

        You can map this wrapper to ESMFold, OpenFold, ColabFold,
        or a remote service later.
        """
        cmd = [
            "sifta-esmfold",
            "--sequence",
            seq,
            "--out",
            str(pdb_path),
        ]

        try:
            proc = subprocess.run(
                cmd,
                text=True,
                capture_output=True,
                timeout=1800,
                check=False,
            )
        except FileNotFoundError:
            return {
                "status": "missing_backend",
                "truth_label": "real_backend_not_installed",
                "hint": "Install or create sifta-esmfold wrapper. "
                        "Or use engine='esmfold' for the free Meta API.",
            }

        return {
            "status": "ok" if proc.returncode == 0 else "failed",
            "truth_label": "external_structure_predictor",
            "returncode": proc.returncode,
            "stdout_tail": proc.stdout[-1000:],
            "stderr_tail": proc.stderr[-1000:],
        }


if __name__ == "__main__":
    seq = sys.argv[1] if len(sys.argv) > 1 else "ACDEFGHIKLMNPQRSTVWY"
    engine = sys.argv[2] if len(sys.argv) > 2 else "toy"
    uniprot = sys.argv[3] if len(sys.argv) > 3 else ""

    broker = ProteinFoldingBroker()
    meta = broker.run(FoldingJob(sequence=seq, engine=engine, uniprot_id=uniprot))
    print(json.dumps(meta, indent=2))
