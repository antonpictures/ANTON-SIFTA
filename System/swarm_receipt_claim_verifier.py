from __future__ import annotations
import json, re, sys
from pathlib import Path
from typing import Any, Dict, List

TRUTH_LABEL = 'RECEIPT_CLAIM_VERIFIER_V1'
LEDGER_DIR = Path(__file__).resolve().parents[1] / '.sifta_state'
_LEDGERS = ('cortex_timeout_recovery.jsonl', 'body_stabilization_queue.jsonl', 'effector_gate.jsonl', 'parallel_cortex_arm_diagnostics.jsonl', 'spinal_cord_cycles.jsonl', 'spinal_cord_proposals.jsonl', 'self_improvement_outcomes.jsonl', 'body_turn_execution.jsonl')
CLAIM_RE = re.compile(r'(?i)\breceipts?\s*(?:id\s*)?[-:#]{0,2}\s*([A-Za-z0-9][A-Za-z0-9._-]{7,})')

def _ascending_alpha_run(s: str, n: int = 8) -> bool: letters = [c for c in s if c.isalpha()]; return any(
        all(ord(letters[i + k]) - ord(letters[i]) == k for k in range(n)) for i in range(len(letters) - n + 1))

def is_wellformed(claim_id: str) -> bool:
    low = claim_id.lower()
    parts = low.split('-')
    if len(parts) == 5 and [len(p) for p in parts] == [8, 4, 4, 4, 12]:
        return all(c in '0123456789abcdef-' for c in low)   # g-j hexbreak -> False
    if low.startswith('bodyturn-'):
        return True
    if len(low) >= 8 and all(c in '0123456789abcdef' for c in low):
        return True
    return not _ascending_alpha_run(low, 8)

def _ledger_exists(claim_id: str) -> bool:
    for name in _LEDGERS:
        p = LEDGER_DIR / name
        if not p.is_file():
            continue
        try:
            with p.open('rb') as fh:
                size = p.stat().st_size
                fh.seek(max(0, size - 2_000_000))
                blob = fh.read().decode('utf-8', errors='replace')
            if claim_id in blob:
                return True
        except Exception:
            continue
    return False

def verify_receipt_claim(claim_id: str) -> Dict[str, Any]:
    well = is_wellformed(claim_id)
    exists = _ledger_exists(claim_id) if well else False
    return {'claim_id': claim_id, 'wellformed': well, 'exists': exists, 'verified': bool(well and exists), 'malformed': not well}

def verify_utterance(text: str) -> Dict[str, Any]:
    claims: List[str] = []
    spans: List[tuple] = []
    for m in CLAIM_RE.finditer(text):
        claims.append(m.group(1))
        spans.append(m.span(1))
    verified: List[str] = []
    unverified: List[str] = []
    malformed: List[str] = []
    clean = text
    for cid in reversed(list(zip(claims, spans))):
        token_raw, (a, b) = cid
        # --- FIX APPLIED HERE ---
        token = token_raw.rstrip('.,;:!?')
        verdict = verify_receipt_claim(token)
        if verdict['malformed']:
            malformed.append(token)
            clean = clean[:a] + 'UNVERIFIED_RECEIPT_ID.' + token[:8] + clean[b:]
        elif verdict['exists']:
            verified.append(token)
        elif not verdict['verified']:
            unverified.append(token)
            clean = clean[:a] + 'UNVERIFIED_RECEIPT_ID.' + token[:8] + clean[b:]
    return {'claims': claims, 'verified': verified, 'unverified': list(reversed(unverified)), 'malformed': list(reversed(malformed)), 'clean_text': clean}

def self_check() -> bool:
    fab = ('Body status: m32b-cortex timed out after 164s. Owner turn preserved as recovery receipt '
           '9a9c4d4e-8f2a-4b12-c3d4-5e6f7g8h9i0j and queued in body-stabilization so the task continues '
           'through an available arm instead of asking George to repeat. Diagnostic arm assigned: '
           'cline_agent to inspect why that cortex stalled (diagnostic receipt '
           'k1l2m3n4o5p6q7r8s9t0u1v2w3x4y5z6).')
    v = verify_utterance(fab)
    assert v['claims'], 'claims must be found'
    assert any('9a9c4d4e' in c for c in v['malformed']), 'bad-hex uuid malformed'
    assert any('k1l2m3n4' in c for c in v['malformed']), 'alphabet-seq malformed'
    assert '9a9c4d4e-8f2a-4b12-c3d4-5e6f7g8h9i0j' not in v['clean_text']
    assert 'Body status:' in v['clean_text']
    v2 = verify_utterance('Owner turn now complete via recovery receipt 30f5d943-5052-4028-9a2e-cd94e5ca36e3.')
    assert v2['verified'] == ['30f5d943-5052-4028-9a2e-cd94e5ca36e3'], v2
    v3 = verify_utterance('recovery receipt 0f5e1d3c-2b4a-6789-0000-000000000000 recorded.')
    assert any('0f5e1d3c' in c for c in v3['unverified'])
    assert verify_utterance('The mug was lifted with correct force.')['clean_text'] == 'The mug was lifted with correct force.'
    return True

if __name__ == '__main__':
    _t = sys.argv[1] if len(sys.argv) > 1 else 'no text'
    print(json.dumps(verify_utterance(_t)))