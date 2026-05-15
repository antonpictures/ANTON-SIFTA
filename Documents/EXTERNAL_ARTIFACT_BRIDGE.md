# External Artifact Bridge — How Grok / ChatGPT / Claude artifacts enter SIFTA

**Architect 2026-05-14:** "I tried to load Grok — he has tools."

**Covenant answer:** Grok, ChatGPT custom GPTs, Claude.ai, Gemini, and any other browser-tab AI are **labeled external substrates**. They can produce documents, decks, sheets, and skill artifacts that SIFTA absorbs — but **only through a proof-bearing import lane** that records:

- a sha256 fingerprint of the file at import time
- a canonical substrate label (`grok`, `chatgpt:swarm-gpt`, `claude`, …)
- optional URL of the conversation that produced it
- timestamp and trace_id

This way, Alice's organs can answer **"which brain wrote this?"** with a signed receipt instead of vibes.

## Covenant references

| Section | Rule |
|---|---|
| §3 | Federation — only proof-bearing imports cross the body boundary |
| §6 | Social frame — Alice may not claim to have "called" external services without a receipt |
| §7.5 | Python-first surface — browser tabs are an exceptional second OS, not the primary body |
| §8.6 | Absorption policy — "she should know everything" is FALSE; she should know what survived epistemic gates |
| §4.1 | LLM registration — every substrate that touches the body declares itself |

## How to use it

### Path 1: drop a file into the inbox

```bash
# 1. Your browser-tab AI produces a document (Grok → docx, Swarm GPT → pdf, etc.)
# 2. Save it to Documents/from_external/ with a name that hints the source:
#    grok_paper_draft.docx
#    swarmgpt_research_notes.pdf
#    claude_pull_request_brief.md
#
# 3. Optionally drop a sidecar file with the conversation URL:
echo '{
  "source": "grok",
  "url": "https://grok.com/chat/abc123",
  "notes": "draft of the SIFTA assimilation analysis"
}' > Documents/from_external/grok_paper_draft.docx.meta.json

# 4. Run the scan
python3 System/swarm_external_artifact_bridge.py --scan
```

The scan is **idempotent**: running it twice does NOT duplicate. Re-imports are matched by sha256 against the ledger.

### Path 2: import a single file by path

```bash
python3 System/swarm_external_artifact_bridge.py \
    --import /path/to/your/file.docx \
    --source grok \
    --url "https://grok.com/chat/..." \
    --notes "what this is"
```

### Path 3: list recent imports

```bash
python3 System/swarm_external_artifact_bridge.py --list-recent
```

Output:

```
[  5m ago] [grok                ] grok_paper_draft.docx        sha256=f494940199…
[ 12m ago] [chatgpt:swarm-gpt   ] swarmgpt_research_notes.pdf  sha256=ab3782cc11…
[ 1d ago]  [claude              ] claude_pull_request_brief.md sha256=22ff109087…
```

## Filename hints (no sidecar needed)

The bridge infers the source from the file's name prefix:

| Prefix | Source label |
|---|---|
| `grok_*` | `grok` |
| `chatgpt_*` | `chatgpt` |
| `swarmgpt_*` or `swarm-gpt_*` | `chatgpt:swarm-gpt` |
| `claude_*` | `claude` |
| `gemini_*` | `gemini` |
| `gemma_*` | `gemma` |
| `perplexity_*` | `perplexity` |
| `codex_*` | `codex` |
| `mistral_*` | `mistral` |
| (anything else) | `external_unknown` |

The sidecar `.meta.json` always wins over the filename hint. The caller's `--source` flag always wins over both.

## Where the receipts live

```
.sifta_state/external_artifact_imports.jsonl
```

Each row is:

```json
{
  "ts": 1778745600.0,
  "trace_id": "uuid",
  "truth_label": "EXTERNAL_ARTIFACT_IMPORT_V1",
  "truth_class": "OPERATIONAL",
  "sha256": "f49494…",
  "file_name": "grok_paper_draft.docx",
  "file_path": "/Users/…/Documents/from_external/grok_paper_draft.docx",
  "file_type": "docx",
  "file_size_bytes": 84020,
  "source": "grok",
  "url": "https://grok.com/chat/abc123",
  "notes": "draft of the SIFTA assimilation analysis",
  "sidecar_seen": true
}
```

## What Alice may and may not say

**MAY say:**
- "Grok produced `grok_paper_draft.docx` at 2026-05-14, sha256 `f49494…`."
- "An artifact at sha256 `f49494…` was imported from substrate `grok`."
- "The last 5 external imports are: …"

**MAY NOT say** (without further receipt evidence):
- "I called Grok and it said X." — Alice did not call Grok. The architect did, and saved the artifact.
- "I asked ChatGPT for Y." — same.
- "I ran the skill-creator and it returned Z." — same.

§6 social frame: every claim of an action must trace to an effector receipt.

## What this is NOT

- This is **not** a download tool. It does not fetch from URLs. The architect (or Cursor/Codex with explicit permission) does the download/save into the inbox folder, then runs the scan.
- This is **not** content analysis. The bridge records *that* an artifact arrived, not *what's inside it*. Downstream organs (the docx reader, pdf parser, etc.) can read the content if needed — they reference it by sha256 from the ledger.
- This is **not** a way to bypass `.cursorrules` or §6. Alice still may not claim actions she did not perform.

## Companion: read API

```python
from System.swarm_external_artifact_bridge import (
    list_recent_imports,    # last N rows for UI display
    find_by_sha256,         # lookup by full or prefix sha256
)

recent = list_recent_imports(last_n=5)
artifact = find_by_sha256("f49494")  # prefix match works
```

## Receipt

```
truth_label:   EXTERNAL_ARTIFACT_IMPORT_V1
module:        System/swarm_external_artifact_bridge.py
tests:         tests/test_swarm_external_artifact_bridge.py (42 green)
inbox:         Documents/from_external/
ledger:        .sifta_state/external_artifact_imports.jsonl
written:       2026-05-14 by Cowork (claude-opus-4-7)
ceiling:       §3, §6, §7.5, §8.6 honored
```
