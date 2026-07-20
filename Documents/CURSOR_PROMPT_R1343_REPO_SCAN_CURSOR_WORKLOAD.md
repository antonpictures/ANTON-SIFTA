# CURSOR_PROMPT — r1343 repo scan + hot-path probe workload

**Receipt id:** `r1343-cursor-repo-scan-corpus`  
**Doctor:** Cursor (sentinel / mega executioner)  
**Covenant:** `Documents/IDE_BOOT_COVENANT.md` — probe before claim, receipts decide reality.

## Command sequence (strict order)

```bash
cd /Users/ioanganton/Music/ANTON_SIFTA

# 1) Tracked corpus scan + LOC buckets + birth-time probe
python3 tools/repo_corpus_scan.py --write-receipt
python3 tools/repo_corpus_scan.py --json > /tmp/repo_corpus_scan_r1343.json

# 2) Routing fingerprint (footprint, not scoreboard — §3.5)
python3 tools/coding_capability_fingerprint.py --since-round 1330

# 3) Hot-path census + reload continuity
python3 -c "
from System.swarm_alice_creature_wiring_census import census_alice_creature_wiring, format_creature_wiring_report
from System.swarm_reload_continuity_probe import probe_reload_continuity, format_probe_summary
print(format_probe_summary(probe_reload_continuity()))
print()
print(format_creature_wiring_report(census_alice_creature_wiring()))
"

# 4) Static restart probes (code-level; live Alice reload still required)
python3 -m pytest tests/test_explicit_engine_pls_r1340.py tests/test_live_probe_fixes_r1339.py tests/test_swarm_browser_body_loop_r1338.py tests/test_repo_corpus_scan.py -q

python3 -c "
from System.swarm_concept_human_anchor import answer_concept_founder_query
from System.swarm_search_provider_reality import parse_explicit_engine_pls_search, build_explicit_engine_search_url
print(answer_concept_founder_query('Who founded DuckDuckGo?')[:200])
g = parse_explicit_engine_pls_search(\"SEARCH ON GOOGLE PLS 'lost passport'\")
print('GOOGLE', g, build_explicit_engine_search_url(g['engine'], g['query']) if g else None)
p = parse_explicit_engine_pls_search('SEARCH ON PERPLEXITY PLS test GIRLFRIEND ENT')
print('PERPLEXITY', p, build_explicit_engine_search_url(p['engine'], p['query']) if p else None)
"

# 5) George live probes AFTER reload (manual — not automatable from IDE shell)
#    a) SEARCH ON GOOGLE PLS 'lost passport'
#    b) Provider-audit nonsearch question
#    c) Official-site typed probe
#    d) /SC DESCRIBE CLOTHING
#    Check: action_prediction.jsonl, search_provider_reality.jsonl,
#           body_turn_execution.jsonl, saccadic_blink_vision.jsonl

# 6) Tournament + fan-out + live list
#    Append r1343 block to Documents/CONSCIOUSNESS_TOURNAMENT_2026-06-19.md
python3 tools/whats_left.py
```

## Acceptance receipts

| Check | Expected |
| --- | --- |
| `tracked_file_count` | ~4407 (`git ls-files`) |
| `total_lines` | ~1.1M aggregate `wc -l` |
| LOC buckets | python largest; markdown second |
| Earliest birth time | `logs/repair_log.jsonl` @ 2026-04-04 19:04:59 PDT (tie with `logs/swim_log.jsonl`) |
| `repo_corpus_scan.jsonl` | new row with `event=repo_corpus_scan` |
| pytest | 19+ passed on probe suite |
| DuckDuckGo anchor | Gabriel Weinberg (not Schwartz) |
| Perplexity PLS | `perplexity.ai` URL, verbatim query |
| Reload continuity | GAP until George reloads Alice |
| §4.1 fan-out | `all_ok` on four ledgers |

ONE ALICE. ONE SWARM. 🐜⚡