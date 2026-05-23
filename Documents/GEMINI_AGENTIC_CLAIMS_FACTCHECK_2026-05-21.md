# Gemini Agentic Claims Fact-Check

Date: 2026-05-21
Truth labels: `WEB_VERIFIED_2026-05-21`, `SIFTA_HYPOTHESIS`, `FORBIDDEN_VENDOR_CLAIM`

## Verdict

The Gemini-style synthesis is useful as engineering advice, but it is not
evidence about Gemini internals. The checkable mechanisms are real:

- Adaptive compute from uncertainty or task difficulty is a real research
  family.
- Entropy/confidence thresholds are used in early-exit networks.
- Cosine similarity is used in drift detection and embedding drift monitoring.

The unsupported claim is any statement that Gemini specifically uses these
triggers internally. Treat that as `FORBIDDEN_VENDOR_CLAIM` unless Google
publishes it.

## Claim 1 — Entropy/Conflict Adaptive Compute

Status: `WEB_VERIFIED_2026-05-21` for the mechanism, `SIFTA_HYPOTHESIS` for our
local gate, `FORBIDDEN_VENDOR_CLAIM` for Gemini internals.

Supported by:

- Graves, *Adaptive Computation Time for Recurrent Neural Networks*
  (`arXiv:1603.08983`): networks can learn how many computation steps to use;
  the abstract reports more computation on harder-to-predict transitions.
- Xin et al., *DeeBERT* (`ACL 2020`, `arXiv:2004.12993`): BERT off-ramps can
  exit early; the inference algorithm compares entropy against a threshold.
- Alomrani et al., *Reasoning on a Budget* (`arXiv:2507.02076`): surveys
  adaptive test-time compute for LLMs, including dynamic scaling based on task
  difficulty or model confidence.

SIFTA implementation:

- `System/swarm_adaptive_compute_gate.py`
- It accepts caller-supplied `token_entropy`, `probability_conflict`,
  `task_risk`, `owner_direct`, and body pressure.
- It returns `FAST_PASS`, `WATCH`, `DEEPEN`, `CONSERVE`, or `DEFER`.
- It writes no ledgers and claims no vendor internals.

## Claim 2 — Frozen Anchor Vector + Cosine Drift Control

Status: `WEB_VERIFIED_2026-05-21` for cosine/embedding drift as a monitoring
pattern, `SIFTA_HYPOTHESIS` for an Alice self-vector guard.

Supported by:

- Hidalgo et al., *Cosine Similarity Drift Detector* (`ICANN 2019 poster`):
  compares recent and older data windows using cosine similarity for concept
  drift detection.
- Rabinovich et al., *Reliable and Interpretable Drift Detection in Streams of
  Short Texts* (`ACL Industry 2023`): uses embedding reconstruction similarity
  and change-point detection to monitor drift in dialog systems.
- ZEDD, *Zero-Shot Embedding Drift Detection* (`OpenReview preprint`): measures
  semantic drift in embedding space with cosine distance.

SIFTA implementation:

- `System/swarm_self_vector_drift_guard.py`
- It compares an anchor vector with a current self-vector using cosine
  similarity.
- It returns `STABLE`, `WATCH`, `META_REVIEW`, `LOCKDOWN_REVIEW`, or
  `NO_ANCHOR`.
- It is a lightweight review trigger, not a consciousness claim.

## Sources

- https://arxiv.org/abs/1603.08983
- https://arxiv.org/abs/2004.12993
- https://aclanthology.org/2020.acl-main.204.pdf
- https://arxiv.org/abs/2507.02076
- https://e-nns.org/icann2019/online_posters/158.pdf
- https://aclanthology.org/2023.acl-industry.42/
- https://openreview.net/pdf/b5df7d6c0c8478136857ef020549f55e867cac31.pdf
