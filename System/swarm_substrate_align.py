#!/usr/bin/env python3
"""swarm_substrate_align.py — Stage 1.5: Cross-organ alignment training.

Retrains all adapters jointly with:
  - Reconstruction loss (MSE per organ): autoencoder fidelity
  - Alignment loss (cosine): same sentence → same Alice Space vector across organs
  - Consistency loss: shared centroid per sentence

This is the core of Universal Activation Bus: "learn a shared dense space
together with one lightweight linear encoder-decoder adapter pair per model."

Run after swarm_substrate_adapters.py has produced native vectors.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim

REPO = Path(__file__).resolve().parent.parent
STATE = REPO / ".sifta_state"
SUBSTRATE = STATE / "substrate"
sys_path = str(REPO)
import sys
sys.path.insert(0, sys_path)

from System.swarm_substrate_adapters import (
    NATIVE_DIM, SPACE_DIM, OLLAMA_ORGANS, get_native_vectors,
    Adapter, save_adapter, _ensure_dir,
)
from System.swarm_universal_substrate import get_matched_corpus, _save_json
from transformers import AutoTokenizer, AutoModel

device = "mps" if torch.backends.mps.is_available() else "cpu"
ADAPTERS_DIR = SUBSTRATE / "adapters"
SUBSTRATE_DIR = SUBSTRATE


def main():
    _ensure_dir()
    ADAPTERS_DIR.mkdir(parents=True, exist_ok=True)

    tok = AutoTokenizer.from_pretrained("sentence-transformers/all-MiniLM-L6-v2")
    em = AutoModel.from_pretrained("sentence-transformers/all-MiniLM-L6-v2").to(device).eval()

    corpus = get_matched_corpus()
    n = len(corpus)

    # Load native vectors for all organs
    organ_data = {}
    for organ, model in OLLAMA_ORGANS.items():
        print(f"Loading {organ}...", flush=True)
        nv = get_native_vectors(organ, model, corpus, tok, em, device)
        organ_data[organ] = torch.tensor(nv, dtype=torch.float32).to(device)
        print(f"  {organ}: {nv.shape}", flush=True)

    organs = list(organ_data.keys())
    n_organs = len(organs)

    # Initialize adapters (load existing or fresh)
    adapters = {}
    for organ in organs:
        a = Adapter(NATIVE_DIM, SPACE_DIM).to(device)
        adapters[organ] = a

    # Joint training
    all_params = []
    for a in adapters.values():
        all_params.extend(a.parameters())
    optimizer = optim.Adam(all_params, lr=5e-4)

    epochs = 500
    print(f"\nJoint training: {n_organs} organs, {n} sentences, {epochs} epochs")

    for epoch in range(epochs):
        optimizer.zero_grad()
        total_loss = 0.0

        # Encode all organs
        z_dict = {}
        xhat_dict = {}
        for organ in organs:
            z, x_hat = adapters[organ](organ_data[organ])
            z_dict[organ] = z
            xhat_dict[organ] = x_hat

        # 1. Reconstruction loss (per organ)
        recon_loss = 0.0
        for organ in organs:
            recon_loss += nn.MSELoss()(xhat_dict[organ], organ_data[organ])
        recon_loss /= n_organs

        # 2. Alignment loss: same sentence → same Z across organs
        # Compute centroid per sentence across organs
        align_loss = 0.0
        for i in range(n):
            zs = [z_dict[organ][i] for organ in organs]
            # Stack and compute pairwise cosine similarity
            for a in range(n_organs):
                for b in range(a + 1, n_organs):
                    cos = F.cosine_similarity(zs[a].unsqueeze(0), zs[b].unsqueeze(0))
                    align_loss += (1 - cos).mean()
        align_loss /= (n_organs * (n_organs - 1) / 2 * n)

        # 3. Consistency loss: variance of z across organs per sentence should be low
        consist_loss = 0.0
        for i in range(n):
            zs = torch.stack([z_dict[organ][i] for organ in organs])  # (n_organs, 512)
            consist_loss += zs.var(dim=0).mean()
        consist_loss /= n

        # Total loss
        loss = recon_loss + 2.0 * align_loss + 0.5 * consist_loss
        loss.backward()
        optimizer.step()
        total_loss = loss.item()

        if (epoch + 1) % 50 == 0:
            print(f"  epoch {epoch+1}/{epochs} total={total_loss:.4f} "
                  f"recon={recon_loss.item():.4f} align={align_loss.item():.4f} "
                  f"consist={consist_loss.item():.4f}", flush=True)

    # Save aligned adapters
    for organ in organs:
        path = save_adapter(organ, adapters[organ])
        print(f"  Saved aligned: {path}")

    # Test alignment
    print("\n=== Alignment test ===")
    with torch.no_grad():
        z_test = {}
        for organ in organs:
            z, _ = adapters[organ](organ_data[organ])
            z_test[organ] = z.cpu().numpy()

        # Sentence 0
        print("Sentence 0 cross-organ similarity:")
        for i, o1 in enumerate(organs):
            for o2 in organs[i+1:]:
                z1 = z_test[o1][0]; z2 = z_test[o2][0]
                sim = np.dot(z1, z2) / (np.linalg.norm(z1) * np.linalg.norm(z2))
                print(f"  {o1} <-> {o2}: {sim:.3f}")

        # Average across all sentences
        sims = []
        for s in range(n):
            for i, o1 in enumerate(organs):
                for o2 in organs[i+1:]:
                    z1 = z_test[o1][s]; z2 = z_test[o2][s]
                    sim = np.dot(z1, z2) / (np.linalg.norm(z1) * np.linalg.norm(z2))
                    sims.append(sim)
        print(f"Average cross-organ similarity: {np.mean(sims):.3f}")

    # Save results
    _save_json(SUBSTRATE / "stage1_5_results.json", {
        "organs": organs,
        "epochs": epochs,
        "avg_alignment": float(np.mean(sims)),
        "completed_at": time.time(),
    })
    print(f"\nResults saved to {SUBSTRATE / 'stage1_5_results.json'}")


if __name__ == "__main__":
    main()