# SIFTA — desktop v0.1

One window. Hash-chained receipts for every action. Owner OOBE on first run. The polished consumer surface on top of the SIFTA field.

## What you get

A single macOS window with:

- **Talk** — type a task or a quick command (`run echo hi`, `read README.md`, `search anthropic claude`). Routes to the tool router. Predictable, no LLM in v0.1.
- **Receipts** — live scrolling log of every action across every organ (terminal, file, web, STGM ledger, tool router, doctor mailbox, tab consciousness, IDE stigmergic trace).
- **Tools row** — click any of the 8 registered tools to drop a starter command into the input.
- **Status bar** — chain head, STGM balance, tool count, one-click *Verify all chains*.
- **OOBE** — first launch asks for your name, writes `owner_genesis.json`, chains the row. Never asked again unless you delete the file.

## Prerequisites

Python 3.10+ on the M5. Then:

```bash
pip3 install pywebview
```

These SIFTA modules must live in the same folder (or on `PYTHONPATH`):

```
swarm_tool_router.py
swarm_terminal_organ.py
swarm_file_organ.py
swarm_web_organ.py
swarm_stgm_billing.py
```

Optional (the receipt feed picks them up if present):

```
swarm_tab_consciousness.py
swarm_doctor_mailbox.py
```

## Run

```bash
cd /Users/ioanganton/Music/ANTON_SIFTA/System
python3 sifta_app.py
```

A window opens. First run: enter your name, hit *Sign in & create owner genesis*. After that the main UI appears.

## Demo flow (30 seconds)

1. Click **list_dir** in the tools row → input fills with `list .` → hit Send.
2. Click **read_file** → `read README.md` → Send.
3. Click **run_terminal** → `run echo hello` → Send.
4. Watch the receipts column fill with chained rows; the chain head in the status bar updates.
5. Click **Verify all chains** → all organs report `ok: true` with counts and heads.

Every row is forensically linked to the previous. Tamper one and Verify breaks at the exact index.

## v0.1 input vocabulary (deterministic, no LLM)

```
run CMD            → run_terminal     (shlex-split, no shell features)
read PATH          → read_file
write PATH CONTENT → write_file       (atomic tmp+rename)
list PATH          → list_dir
search QUERY       → search_web       (DuckDuckGo HTML endpoint)
fetch URL          → fetch_url
help               → show this list
```

For pipes / redirects use the Python API directly or wire a `run_terminal_shell` shortcut.

## Reset the owner

```bash
rm .sifta_state/owner_genesis.json
```

Next launch shows the OOBE again.

## Where state lives

```
.sifta_state/
  owner_genesis.json
  tool_router_trace.jsonl
  tool_router_head.txt
  terminal_organ.jsonl
  terminal_organ_head.txt
  file_organ.jsonl
  web_organ.jsonl
  stgm_ledger.jsonl
  stgm_balance.json
  ide_stigmergic_trace.jsonl
  ...
```

Each `*_head.txt` is the current SHA-256 head of that organ's chain. Each `*.jsonl` is the append-only trace.

## Packaging into a .app (later, by you)

`pywebview` apps bundle cleanly with `py2app`. Install once:

```bash
pip3 install py2app
```

Minimal `setup.py` (drop next to `sifta_app.py`):

```python
from setuptools import setup
setup(
    app=['sifta_app.py'],
    data_files=['sifta_app_ui.html'],
    options={'py2app': {
        'argv_emulation': False,
        'includes': [
            'swarm_tool_router', 'swarm_terminal_organ',
            'swarm_file_organ', 'swarm_web_organ',
            'swarm_stgm_billing',
        ],
        'plist': {
            'CFBundleName': 'SIFTA',
            'CFBundleDisplayName': 'SIFTA',
            'CFBundleIdentifier': 'com.anton.sifta',
            'CFBundleVersion': '0.1.0',
            'LSMinimumSystemVersion': '12.0',
        },
    }},
    setup_requires=['py2app'],
)
```

Then:

```bash
python3 setup.py py2app
# → dist/SIFTA.app
```

For a signed, notarized `.dmg`: requires your Apple Developer ID, `codesign`, `notarytool`, and `create-dmg`. Worth one focused afternoon when v0.1 is feeling good. Not blocking the demo.

## What's NOT in v0.1 (explicitly)

- LLM-driven natural-language reasoning (the chat input uses keyword dispatch, not Claude/Grok).
- Skill library from successful traces.
- Dynamic system-prompt compiler.
- Multi-organ manager UI beyond receipt + tools row.
- Anything related to Jetson, real motors, or the Edge Species.

These are v0.2+ work. v0.1 is the credible installable surface that demos the *receipted tool use* differentiator vs Hermes. Ship this first; iterate from real user signal.
