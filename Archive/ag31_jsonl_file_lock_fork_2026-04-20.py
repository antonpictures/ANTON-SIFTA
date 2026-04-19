# Preserved fork from AG31 (Antigravity) — 2026-04-20
# Added ecdsa-backed DualIDEStigmergicIdentity and inlined record_mutation.
# That fork broke the stable API: append_line_locked(path, line) used by
# ide_stigmergic_bridge + ~30 modules, and required `pip install ecdsa`.
# Canonical lock restored in System/jsonl_file_lock.py; canonical mutation
# API remains System/swarm_ssp_mutation_record.record_mutation.
# Do not import this file from production code — reference only.
