# System/sifta_protein_folding_broker.py

from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import json
import hashlib
import os
import subprocess
import sys


AA20 = set("ACDEFGHIKLMNPQRSTVWY")


@dataclass
class FoldingJob:
    sequence: str
    name: str = "sifta_protein"
    engine: str = "toy"  # toy | c55m_hp_lattice | esmfold_cli | external_pdb
    out_dir: str = ".sifta_state/protein_folds"


class ProteinFoldingBroker:
    """
    SIFTA protein folding broker.

    Honest modes:
      toy          = local Monte Carlo CA-backbone demo
      c55m_hp_lattice = deterministic HP lattice beam-search baseline
      esmfold_cli  = calls a local ESMFold/OpenFold-style command if installed
      external_pdb = registers an already-produced PDB from AlphaFold/ESMFold/etc.

    This broker does not pretend toy physics is AlphaFold.
    It makes the app upgradeable.
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
        seq = self.validate_sequence(job.sequence)
        out = Path(job.out_dir)
        out.mkdir(parents=True, exist_ok=True)

        jid = self.job_id(seq, job.engine)
        pdb_path = out / f"{jid}.pdb"
        meta_path = out / f"{jid}.json"

        if job.engine == "toy":
            result = self._run_toy(seq, pdb_path)
        elif job.engine == "c55m_hp_lattice":
            result = self._run_c55m_hp_lattice(seq, pdb_path)
        elif job.engine == "esmfold_cli":
            result = self._run_esmfold_cli(seq, pdb_path)
        else:
            raise ValueError(f"unknown engine: {job.engine}")

        meta = {
            "job_id": jid,
            "name": job.name,
            "engine": job.engine,
            "sequence": seq,
            "length": len(seq),
            "pdb_path": str(pdb_path),
            **result,
        }

        meta_path.write_text(json.dumps(meta, indent=2))
        self.jobs.append(meta)
        return meta

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
                "hint": "Install or create sifta-esmfold wrapper.",
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

    broker = ProteinFoldingBroker()
    meta = broker.run(FoldingJob(sequence=seq, engine=engine))
    print(json.dumps(meta, indent=2))
