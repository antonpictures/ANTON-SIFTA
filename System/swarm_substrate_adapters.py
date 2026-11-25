#!/usr/bin/env python3
"""swarm_substrate_adapters.py — Stage 1: Train per-organ adapter pairs.

For each Ollama organ:
  1. Feed the 18 matched corpus sentences
  2. Generate a response (captures the organ's "understanding")
  3. Embed input + response with MiniLM → native understanding vector
  4. Train encoder (native_dim → 512) and decoder (512 → native_dim)
  5. Save adapter to .sifta_state/substrate/adapters/

Universal Activation Bus approach:
  - Shared space Z (512-dim) is frozen after training
  - Each organ gets one encoder-decoder pair
  - New organs onboard by fitting only their adapter pair
  - Same sentence across organs → close in Z (alignment loss)

Local-first. No cloud. Runs on George's Mac (MPS/CPU).
"""
from __future__ import annotations

import json
import time
import urllib.request
from pathlib import Path
from typing import Optional

import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from transformers import AutoTokenizer, AutoModel

REPO = Path(__file__).resolve().parent.parent
STATE = REPO / ".sifta_state"
SUBSTRATE = STATE / "substrate"
ADAPTERS_DIR = SUBSTRATE / "adapters"
SPACE_DIM = 512
MINILM_DIM = 384  # all-MiniLM-L6-v2 hidden size

# Native dim = MiniLM embedding of (input + response) = 384 * 2 = 768
# We use a single 768-dim vector per sentence per organ
NATIVE_DIM = 768

ORGANS = {
    "AliceG4U": "AliceG4U:latest",
    "lfm3-omni": "lfm3-omni:latest",
    "qwen3-1.7b": None,  # not in Ollama, skip for now
    "songe-gemma4": None,  # not in Ollama directly
    "songe-minicpm": None,
}

# Only test organs that are actually in Ollama
OLLAMA_ORGANS = {
    "AliceG4U": "AliceG4U:latest",
    "lfm3-omni": "lfm3-omni:latest",
    "bonsai-2": "bonsai-2:latest",
    "nemotron-3.5": "nemotron-3.5-bolt:e4b",
}

import sys
sys.path.insert(0, str(REPO))
from System.swarm_universal_substrate import get_matched_corpus, _ensure_dir, _load_json, _save_json, register_organ


def ollama_generate(model: str, prompt: str, timeout: float = 60.0) -> str:
    """Generate a response from an Ollama model."""
    payload = json.dumps({
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"num_predict": 64, "temperature": 0.3},
    }).encode()
    req = urllib.request.Request(
        "http://localhost:11434/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read())
        return data.get("response", "").strip()


class Adapter(nn.Module):
    """Per-organ adapter: encoder (native → 512) + decoder (512 → native)."""

    def __init__(self, native_dim: int, space_dim: int = SPACE_DIM):
        super().__init__()
        self.encoder = nn.Sequential(
            nn.Linear(native_dim, space_dim * 2),
            nn.GELU(),
            nn.Linear(space_dim * 2, space_dim),
        )
        self.decoder = nn.Sequential(
            nn.Linear(space_dim, space_dim * 2),
            nn.GELU(),
            nn.Linear(space_dim * 2, native_dim),
        )

    def encode(self, x: torch.Tensor) -> torch.Tensor:
        return self.encoder(x)

    def decode(self, z: torch.Tensor) -> torch.Tensor:
        return self.decoder(z)

    def forward(self, x: torch.Tensor):
        z = self.encode(x)
        x_hat = self.decode(z)
        return z, x_hat


def embed_text(tokenizer, model, text: str, device: str = "cpu") -> np.ndarray:
    """Embed text using MiniLM, mean-pooled."""
    inputs = tokenizer(text, return_tensors="pt", truncation=True,
                       max_length=128, padding=True).to(device)
    with torch.no_grad():
        outputs = model(**inputs)
    # Mean pool over tokens
    mask = inputs["attention_mask"].unsqueeze(-1).float()
    summed = (outputs.last_hidden_state * mask).sum(dim=1)
    counts = mask.sum(dim=1).clamp(min=1)
    emb = (summed / counts).squeeze(0).cpu().numpy()
    return emb


def get_native_vectors(organ_name: str, model_name: str,
                       corpus: list[str], tokenizer, embed_model, device: str) -> np.ndarray:
    """For each sentence, generate a response and embed input+response.

    Returns: (n_sentences, 768) array — concatenation of input emb + response emb.
    """
    vectors = []
    for i, sentence in enumerate(corpus):
        print(f"  [{i+1}/{len(corpus)}] {sentence[:50]}...", flush=True)
        try:
            response = ollama_generate(model_name, sentence)
        except Exception as e:
            print(f"    WARN: generation failed: {e}", flush=True)
            response = ""
        input_emb = embed_text(tokenizer, embed_model, sentence, device)
        resp_emb = embed_text(tokenizer, embed_model, response if response else sentence, device)
        vec = np.concatenate([input_emb, resp_emb])  # 768-dim
        vectors.append(vec)
        print(f"    response: {response[:60]}", flush=True)
    return np.array(vectors, dtype=np.float32)


def train_adapter(organ_name: str, native_vectors: np.ndarray,
                  epochs: int = 200, lr: float = 1e-3, device: str = "cpu") -> Adapter:
    """Train an adapter: autoencoder + alignment.

    Loss = reconstruction (MSE) + alignment (cosine similarity across organs).
    For Stage 1, we only have one organ at a time, so alignment is handled
    by a shared target: all organs' encodings of the same sentence should
    converge to the same Alice Space vector. We enforce this via a
    consistency loss across organs (computed in a later multi-organ pass).

    For now: autoencoder loss only. Alignment added when all organs are trained.
    """
    n = len(native_vectors)
    x = torch.tensor(native_vectors, dtype=torch.float32).to(device)

    adapter = Adapter(NATIVE_DIM, SPACE_DIM).to(device)
    optimizer = optim.Adam(adapter.parameters(), lr=lr)
    criterion = nn.MSELoss()

    for epoch in range(epochs):
        adapter.train()
        optimizer.zero_grad()
        z, x_hat = adapter(x)
        loss = criterion(x_hat, x)
        # L2 regularization on z to keep space bounded
        loss = loss + 0.001 * (z ** 2).mean()
        loss.backward()
        optimizer.step()

        if (epoch + 1) % 50 == 0:
            print(f"    epoch {epoch+1}/{epochs} loss={loss.item():.4f}", flush=True)

    return adapter


def save_adapter(organ_name: str, adapter: Adapter) -> str:
    """Save adapter weights to disk."""
    ADAPTERS_DIR.mkdir(parents=True, exist_ok=True)
    path = ADAPTERS_DIR / f"{organ_name}.pt"
    torch.save(adapter.state_dict(), path)
    return str(path)


def load_adapter(organ_name: str, device: str = "cpu") -> Optional[Adapter]:
    """Load adapter from disk."""
    path = ADAPTERS_DIR / f"{organ_name}.pt"
    if not path.exists():
        return None
    adapter = Adapter(NATIVE_DIM, SPACE_DIM).to(device)
    adapter.load_state_dict(torch.load(path, map_location=device, weights_only=True))
    adapter.eval()
    return adapter


def main():
    _ensure_dir()
    ADAPTERS_DIR.mkdir(parents=True, exist_ok=True)

    device = "mps" if torch.backends.mps.is_available() else "cpu"
    print(f"Device: {device}")

    # Load MiniLM
    print("Loading MiniLM embedding model...")
    tokenizer = AutoTokenizer.from_pretrained("sentence-transformers/all-MiniLM-L6-v2")
    embed_model = AutoModel.from_pretrained("sentence-transformers/all-MiniLM-L6-v2").to(device)
    embed_model.eval()

    corpus = get_matched_corpus()
    print(f"Corpus: {len(corpus)} sentences")

    results = {}
    for organ_name, model_name in OLLAMA_ORGANS.items():
        print(f"\n=== {organ_name} ({model_name}) ===")
        try:
            # Step 1: Get native vectors
            native_vecs = get_native_vectors(
                organ_name, model_name, corpus, tokenizer, embed_model, device
            )
            print(f"  Native vectors: {native_vecs.shape}")

            # Step 2: Train adapter
            adapter = train_adapter(organ_name, native_vecs, epochs=300, lr=1e-3, device=device)

            # Step 3: Save
            path = save_adapter(organ_name, adapter)
            print(f"  Saved: {path}")

            # Step 4: Register
            register_organ(organ_name, NATIVE_DIM, adapter_path=path)

            # Step 5: Test round-trip
            adapter.eval()
            with torch.no_grad():
                x = torch.tensor(native_vecs[0:1], dtype=torch.float32).to(device)
                z, x_hat = adapter(x)
                mse = ((x_hat - x) ** 2).mean().item()
            print(f"  Round-trip MSE: {mse:.4f}, Z norm: {z.norm().item():.2f}")

            results[organ_name] = {"status": "ok", "path": path, "mse": mse}
        except Exception as e:
            print(f"  FAILED: {e}", flush=True)
            results[organ_name] = {"status": "failed", "error": str(e)}

    print("\n=== Summary ===")
    for name, r in results.items():
        print(f"  {name}: {r['status']}" + (f" (MSE={r.get('mse', '?'):.4f})" if r['status'] == 'ok' else f" ({r.get('error', '?')[:60]})"))

    # Save results
    _save_json(SUBSTRATE / "stage1_results.json", results)
    print(f"\nResults saved to {SUBSTRATE / 'stage1_results.json'}")


if __name__ == "__main__":
    main()