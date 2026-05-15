# `Documents/from_external/` — drop zone for browser-tab AI artifacts

Drop files produced by external AI substrates here:

- Grok docs / sheets
- ChatGPT custom GPT outputs (e.g., Swarm GPT)
- Claude.ai artifacts
- Gemini briefings
- Anything else from a browser-tab AI

Name files with a substrate prefix so the bridge can label them:

- `grok_*.docx`
- `swarmgpt_*.pdf`
- `claude_*.md`
- `gemini_*.xlsx`

Then run:

```bash
python3 ../../System/swarm_external_artifact_bridge.py --scan
```

For per-file metadata (URL of the source conversation, notes), add a sidecar:

```
grok_paper_draft.docx
grok_paper_draft.docx.meta.json
```

Where the sidecar contains:

```json
{
  "source": "grok",
  "url": "https://grok.com/chat/abc123",
  "notes": "draft of the SIFTA assimilation analysis"
}
```

See `Documents/EXTERNAL_ARTIFACT_BRIDGE.md` for the full doctrine.
