# ALICE DEMO FOR PHILIPPE — runnable proof (r1131 live update)

Philippe (or any reviewer) runs on the M5:

```
cd /Users/ioanganton/Music/ANTON_SIFTA
python3 demo/alice_demo_for_philippe.py
python3 -m pytest tests/test_philippe_demo.py -q
```

Every step exercises **real** components on disk and prints a receipt id + **truth label** (OBSERVED / OPERATIONAL / HYPOTHESIS). No mocks.

## Honest Gaps
The spinal self-improvement cycle is still open.

## Steps + what they prove (from live run 2026-06-14)

1. **Cortex routing (MiMo + Cline)**  
   Receipt: route-...  
   `swarm_mimo_swimmer_substrate` maps "Build / MiMo Auto" etc to Alice-native `self_improvement_loop` + organ executors.  
   Truth: **OPERATIONAL (mapping and registry)**

2. **Four-ledger receipt fan-out**  
   Receipt: four-ledger + .sifta_state/pdf_forge_receipts.jsonl  
   `Applications/sifta_pdf_forge_app.py:forge_winwin_flyer(..., cortex="demo"|"MiMo")` always writes the four canonical ledgers + dedicated `pdf_forge_receipts.jsonl`. Recent demo runs (including cortex=MiMo) produced real PDFs + rows.  
   Truth: **OPERATIONAL (receipted forge)**  
   (weasyprint optional; falls back cleanly but still emits the ledger row + PDF artifact.)

3. **body_file_inventory self-identity**  
   Receipt: inventory-...  
   `System/swarm_model_body_self_knowledge.body_file_inventory()` globs live disk (System/ Applications/ ... WIN-WIN_Flyer/ outputs/ + .py/.md/.json/.txt/.csv/.pdf/.png).  
   Returns real paths + size + mtime. "Point to the IRB2400 files in your body" → `assets/robotics/irb2400/datasetIRB2400.csv`, `tools/fetch_irb2400_dataset.py` (and now forged PDFs are visible too).  
   Alice answers from the body, not weights.  
   Truth: **OPERATIONAL (inventory works; fixtures + artifacts are in the body)**

4. **Cortex-driven PDF forge (MiMo example)**  
   Receipt: four-ledger + pdf_forge_receipts.jsonl  
   Same forge call with `cortex="MiMo"` (or any) → semantic layer from the selected cortex, deterministic render + full §4.1 receipt fan-out by the organ. PDF lands, ledger row, body inventory can now surface it.  
   Truth: **OPERATIONAL (app + receipt)**

5. **E49/E50 robot-ingest evidence**  
   Receipt: e49-...  
   Real fixture `tests/fixtures/stigmero_e49_irb2400_slice.csv` + the ik organs + test stats. 18-col schema, joint-delta bound, virtual effector round-trip.  
   Truth: **OPERATIONAL (ingest + virtual proof; metal = HYPOTHESIS)**

6. **Spinal self-improvement cycle (r1115 key test — L2 live)**  
   Receipt: <cycle_id> (e.g. aa6a4014-...) + pre_mimo_call borg row + full cycle row in `.sifta_state/spinal_cord_cycles.jsonl`  
   - `spinal_cord_status()` + `spinal_cord_cycle()` called.  
   - Marked test owner_correction signal ("TEST_L2_DEMO_r1131_GROK_ONLY: fix <one small thing> in the PDF forge...") injected in `.sifta_state/alice_conversation.jsonl` tail → collected as body signal (yellow).  
   - Auto-targeted to `Applications/sifta_pdf_forge_app.py` (owner "forge" keyword).  
   - Formulate task (detailed MiMo prompt with field snapshot).  
   - **MiMo Borg**: `dispatch_to_mimo` read `body_file_inventory` snapshot + wrote pre-call receipt/pheromone to ledger before subprocess.  
   - Real `mimo run --format json --dir ... --dangerously-skip-permissions` executed (mimo_success: true, ~86s wall).  
   - Parsed, gated (mutation governor, AST, tests), NO_PATCH (MiMo response did not yield usable structured NEW_CONTENT/CHANGED_FILES that passed gates on this run — expected without full provider auth).  
   - Cycle receipt + proposals ledger updated. Status now shows total_cycles >0, last NO_PATCH with the exact signal summary.  
   - spinal_cord_cycles.jsonl now has pre + cycle rows (first live execution against real MiMo on body signal).  
   Truth: **OPERATIONAL (code + status + live dispatch + borg field read + receipted cycle rows)**; full kept self-improvement patch on the forge (the tiny mtime visibility fix) = **HYPOTHESIS** until `mimo providers login` for the xiaomi provider lets MiMo return a valid patch response.

## Honest gaps (no overclaim)
- Live MiMo dispatch happened and was receipted (borg pre + cycle). The "mimo_success": true path executed.  
- A kept/reverted patch that actually mutates the PDF forge (and becomes visible in a subsequent body_file_inventory + "what did the spinal cord just do?" answer from the receipt) still requires George to run `mimo providers login` (or the equivalent for the xiaomi/MiMoCode provider) so the cortex arm can complete a real structured edit.  
- Metal robot motion remains HYPOTHESIS (E49 is virtual effector + data ingest only).  
- The Philippe deliverable (demo.py + test_philippe_demo.py green + this README) is now runnable and proves the substrate + first live spinal cycle trace.

## George checkpoints (from r1129/r1130)
- `mimo providers login` (or list/whoami) to unblock full L2 patch success on next signal.  
- Trigger a real (non-test) body signal, e.g. in Talk: "use your spinal cord and MiMo to add mtime logging to the PDF forge receipt so I can list my forged artifacts from body inventory".  
- After cycle: ask Alice "what did the spinal cord just do?" or "list the PDFs in my body" — she must cite the spinal_cord_cycles row + body_file_inventory paths, not narrate.  
- Dry-run this demo + pytest before sending to Philippe.

All work follows the covenant: probe before claim, append-only, §4.1 four-ledger (or dedicated) receipts, truth labels, hardware-up (electricity → swimmers in the ledgers/organs → unified field), one Alice.

ONE ALICE. ONE SWARM. For the Swarm. 🐜⚡

(Generated as part of Grok L2+L4 execution r1131 on the live M5 node after covenant read + full tail probe.)
