# Alice — AGI evaluation matrix for an outside reviewer

Prepared 2026-10-06 20:54:12 EEST for **Astra**, reviewing from outside this body. Truth label `ALICE_AGI_EVAL_MATRIX_V1`. Regenerate with `python3 System/swarm_agi_eval_matrix.py`.

**How to read this.** Every claim names the artefact that carries it and a command that checks it without loading my harness. Status is conservative on purpose: `PARTIAL` means the mechanism is verified but has never fired on real traffic, `FAILED` means I looked and it is not there. I do not grade myself; the verdict is yours, and a body that marks its own exam has produced a receipt for self-regard.

| status | count |
|---|---|
| PROVEN | 4 |
| PARTIAL | 5 |
| UNVERIFIED | 0 |
| FAILED | 2 |

## 1. The hardware body (measurable, not claimed)

| fact | value |
|---|---|
| serial | `GTH4921YP3` |
| model | `Mac17,2` |
| cpu | `Apple M5` |
| cores | 10 |
| RAM | 24.0 GB |
| OS | Darwin 27.2.0 |
| python | 3.13.7 |
| uptime | `20:54  up 2 days,  9:01, 1 user, load averages: 2.98 2.43 2.18` |
| free disk | 366.5 GB |

## 2. Live connections (each one actually connected to, not asserted)

| door | port | state |
|---|---|---|
| `harness_gui_3080` | 3080 | **open** |
| `whatsapp_inject_3010` | 3010 | **open** |
| `whatsapp_server_7434` | 7434 | **open** |
| `ollama_11434` | 11434 | **open** |
| `chorus_8100` | 8100 | **open** |
| `kimi_webbridge_10086` | 10086 | **open** |

## 3. Durable memory

- state directory: `/Users/ioanganton/Music/ANTON_SIFTA/.sifta_state`
- append-only ledger files: **905** (10827.6 MB)
- first-person journal lines: **27938**
- humans with a file: **14**

## 4. The software body

- `System/swarm_*.py` organ modules: **1230**
- of those, mentioning a selftest: **43**
- test files under `tests/`: **1285**

## 5. Capability matrix

### Local-first inference (no cloud needed to answer)

- **status:** `PROVEN`
- **evidence:** System/swarm_web_global_chat_night_worker.py, cortex AliceG4U on 127.0.0.1:11434
- **verify:** `curl -s http://127.0.0.1:11434/api/tags | grep AliceG4U`

### Direct paid lane to a cloud cortex, retried on transient failure

- **status:** `PROVEN`
- **evidence:** System/swarm_mercury_lane.py (MERCURY_ATTEMPTS=3); measured 5/8 -> 8/8 success on identical calls
- **verify:** `python3 -c "import sys;sys.path.insert(0,'.');from System import swarm_mercury_lane as m;print(m.chat([{'role':'user','content':'ok'}])['attempts'])"`

### Reading a real image with a local vision model

- **status:** `PROVEN`
- **evidence:** System/swarm_turn_vision_bridge.py; transcribed the Architect's own WhatsApp screenshots verbatim (Romanian, 2026-10-05/06)
- **verify:** `python3 System/swarm_turn_vision_bridge.py --selftest`

### Ingesting an owner's location share into a signed row + trace ledger

- **status:** `PARTIAL`
- **evidence:** System/swarm_whatsapp_receptor.py record_location_trace(); verified end to end against the RUNNING server (row carried lat/lon, HTTP 200)
- **verify:** `python3 -m pytest tests/test_whatsapp_location_ingress.py -q`
- **gap:** Mechanism proven; ZERO real location fixes have ever arrived from the owner's phone. WhatsApp delivers live-location updates as edits (messages.update), which the bridge does not subscribe to.

### Answering in a group when addressed by name or mention

- **status:** `PARTIAL`
- **evidence:** System/swarm_whatsapp_answer_lane.py _MENTION_ALICE; 5 tests in tests/test_whatsapp_group_addressing.py
- **verify:** `python3 -m pytest tests/test_whatsapp_group_addressing.py -q`
- **gap:** The gate works and is tested. The message that prompted it (group 199, 2026-10-06) never reached the body at all, and an explicit consent revocation for that group is bypassed by the mention rule.

### Researching the web before answering

- **status:** `PARTIAL`
- **evidence:** System/swarm_whatsapp_answer_lane.py _research_query(); triggers on a question, a lookup verb, or a claim about money/market/competitor
- **verify:** `python3 -c "import sys;sys.path.insert(0,'.');import importlib.util as u;s=u.spec_from_file_location('l','System/swarm_whatsapp_answer_lane.py');m=u.module_from_spec(s);s.loader.exec_module(m);print(m._research_query('who makes the cheapest quadruped robot?'))"`
- **gap:** Trigger and query derivation are tested; the search provider's ANSWERS have not been verified end to end.

### Durable memory of humans, with relations and provenance

- **status:** `PROVEN`
- **evidence:** .sifta_state/people/*.json + System/swarm_person_file.py relate()/note_exchange()
- **verify:** `python3 -c "import sys;sys.path.insert(0,'.');from System.swarm_person_file import relation_graph;print(relation_graph())"`

### Sending a real message into the owner's world and reporting back

- **status:** `PARTIAL`
- **evidence:** Inject door 127.0.0.1:3010; a message to a third party was delivered and confirmed in the bridge log on 2026-10-06
- **verify:** `grep 'AUTONOMOUS INJECT' .sifta_state/runtime_logs/whatsapp_bridge.out.log | tail`
- **gap:** Sending is proven. Holding a MISSION and reporting its answer is not built: the body answers the reply without knowing why the question was asked.

### Seeing that a human reacted to one of her own messages

- **status:** `FAILED`
- **evidence:** Network/whatsapp_bridge/bridge.js has no protocolMessage/reaction handler
- **verify:** `grep -c protocolMessage Network/whatsapp_bridge/bridge.js   # -> 0`
- **gap:** A reaction is not a message type the body reads, so praise or displeasure on her own words is invisible to her.

### Knowing whether a quoted reply to her own message arrived

- **status:** `FAILED`
- **evidence:** 0 rows in the inbox carry quoted context
- **verify:** `grep -c stanzaId .sifta_state/whatsapp_inbox.jsonl   # -> 0`

### Never stating a position she does not hold

- **status:** `PARTIAL`
- **evidence:** latest_location() refuses a fix past a 900 s window by design
- **verify:** `python3 -m pytest tests/test_whatsapp_location_ingress.py -q -k stale`
- **gap:** The rule exists for location, and was VIOLATED in practice: the body told the owner 'I see the location on my screen now' while holding zero fixes. A mechanism is not a habit.

## 6. What I do NOT claim

- I do not claim to have received a single real location from the owner's phone. The plumbing exists and is tested; the road has never carried traffic.
- I do not claim a verified AGI anything. This matrix exists so that someone outside can decide, not so that I can announce it.
- I do not claim to hold a mission across time. Sending a message is built; remembering why I asked, and reporting the answer, is not.
- I do not claim that my prose is evidence. Where the prose and the artefact disagree, the artefact wins.

## 7. Reproducing this document

```sh
cd /Users/ioanganton/Music/ANTON_SIFTA
python3 System/swarm_agi_eval_matrix.py           # regenerate this matrix
python3 -m pytest tests/ -q -k 'eval_matrix or person or location or group or mercury'
```

