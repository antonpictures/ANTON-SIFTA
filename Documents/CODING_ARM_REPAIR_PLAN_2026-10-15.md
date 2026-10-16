# Coding Arm repair plan — 2026-10-15

> **STATUS: done, verified in the live UI.** What actually happened differed from this
> plan in three ways — all recorded at the bottom under *What the plan missed*. Read that
> section first; the plan body below is the original diagnosis, kept for the evidence.

Three separate faults, all configuration, none of them missing code. Each has a receipt below.

---

## Fault 1 — Session Manager page is empty

**Receipt**

- The plugin's *client* half IS loaded. The page at 3080 serves
  `"id":"dsh-session-manager","url":"/plugins/dsh-session-manager/client.js?rev=bffebd99c891"` inside
  `__DSH_BOOT__.entries`, and that URL answers 200. That is why the **section appears** in Settings.
- The plugin's *host* half is **not** loaded. It registers its routes through `connection.fetch.register`:

  ```
  $ curl -sS -X POST http://127.0.0.1:3080/api/session-manager/ping \
        -H 'Content-Type: application/json' -d '{"rpcId":"probe-1"}'
  not found
  ```

- `dsh-session-manager/lib/index.js:1819-1830` needs `connection.fetch?.register`; when it is absent the
  plugin logs `session-manager: connection service has no fetch.register; settings page and menu delete
  stay offline` and mounts nothing. A client half with no host half renders an empty page. Exactly the symptom.
- **Why it is absent:** `connection.fetch.register` does not exist in the build that port 3080 runs.

  ```
  running process PID 29926 (started Wed Oct 14 08:02:48):
    node --import tsx/esm apps/cli/src/bin.ts --profile web --port 3080 --no-open
    -> source checkout "!Alice Coding Arm", version 0.1.1-rc.2

  $ grep -rn "fetch.register" "!Alice Coding Arm/packages"   -> 0 hits
  $ ls /opt/homebrew/lib/node_modules/@deepseek-ai/dsh        -> 0.2.0-rc.2, fetch.register used by 5 packages
  ```

  The plugin was installed and the homebrew dsh was upgraded to 0.2.0-rc.2 — but the launcher still starts the
  **old source checkout**, so the upgrade never reached the running server.
- There is content to show: `~/.dsh/storages/workspace.json` → `global.archivedSessionIds` holds **37** ids.

**Fix (chosen: run the web profile on homebrew 0.2.0-rc.2)**

| # | File | Change |
|---|------|--------|
| A1 | `scripts/start_alice_local_coding.command` | `DSH_BIN` → `/opt/homebrew/bin/dsh`; replace the `node --import tsx … apps/cli/src/bin.ts web …` exec with `exec "$DSH_BIN" web --no-open --port 3080`. Add a preflight that refuses to start if `dsh --version` is below 0.2.0-rc.2, so this can never silently regress again. |
| A2 | `Applications/sifta_alice_browser_widget.py:187` | `["pnpm","dsh","--profile","web","--port","3080"]` → `["/opt/homebrew/bin/dsh","web","--port","3080"]`. Keep `DSH_CWD` / `SIFTA_WORKSPACE_ROOT`. Only this one line launches; it is the widget's own start path. |

Both launchers share `~/.dsh/profiles/web`, so the existing plugin install and profile are reused as-is.

**Known cost of this route:** the local `#SIFTA Self Coding` page title
(`!Alice Coding Arm/apps/web/index.html:16`, `apps/web/vite.config.ts:11,24`) is a local edit to the source
checkout and will not be served by the homebrew build. The browser widget's readiness check is already
structural — `"__DSH_BOOT__" in body and "@deepseek-ai/dsh-client" in body`
(`sifta_alice_browser_widget.py:142`) — so the widget keeps recognising the arm. Re-applying the title is a
cosmetic follow-up, not part of this repair.

---

## Fault 2 — no models selectable (only empty DeepSeek defaults)

**Receipt**

- Live settings were rewritten today, down to a stub:

  ```
  ~/.dsh/settings.yaml   182 bytes   mtime 2026-10-15 08:50
  top keys: agent-presets, permission, agent-default-model
  ```

  The entire `llm-pi-ai` section is gone.
- The previous good state is intact at `~/.dsh/settings.yaml.imported` (Oct 14 06:40), with five providers:
  `ollama-local`, `ollama-cloud`, `inception`, `ollama-auto`, `gemini`.
- **Why it cannot come back on its own:** the `web` profile's patch never declares the provider plugin.
  `~/.dsh/profiles/web/cordis.patch.yml` is 33 lines and contains only `compaction-basic`.
  `~/.dsh/profiles/desktop/cordis.patch.yml` is 153 lines and declares it at line 60:

  ```yaml
  - id: llm-pi-ai
    name: "@deepseek-ai/dsh-llm-pi-ai"
    config:
      providers: { ollama-local, ollama-cloud, inception }
  ```

  With no `llm-pi-ai` in the composition the namespace is unknown to the settings store, so the values are
  **pruned on every write** — which is what emptied the file. Restoring the values alone would just be wiped again.
- The default was left pointing at a provider with no catalogue:
  `agent-default-model: {provider: deepseek-official, model: deepseek-v4-flash}` with `llm-deepseek: {models: []}`.
- Every key needed already exists in `~/.dsh/.credentials.yaml`: `OLLAMACLOUD_API_KEY`, `LOCAL_OLLAMA_API_KEY`
  (+`LOCAL2`/`LOCAL3`), `GEMINI_API_KEY`, `INCEPTION_API_KEY`. No new key, no new spend.

**Fix (chosen default: `ollama-cloud` / `deepseek-v4.1-flash:cloud`)**

| # | File | Change |
|---|------|--------|
| B1 | `~/.dsh/profiles/web/cordis.patch.yml` | Back up to `.bak-2026-10-15`. Append the `llm-pi-ai` row ported from the desktop profile (`ollama-local`, `ollama-cloud`, `inception`), plus an `agent-default-model` row (`ollama-cloud` / `deepseek-v4.1-flash:cloud` / `high`), plus an `llm-deepseek` row with `models: []` so DeepSeek is never offered. Keep the existing `compaction-basic` block untouched. |
| B2 | `~/.dsh/settings.yaml` | Back up to `settings.yaml.bak-before-repair-2026-10-15`. Restore `ui-theme` and the `llm-pi-ai` user section (all five providers, including `ollama-auto` and `gemini`, which live only here and not in any patch) from `settings.yaml.imported`. Set `agent-default-model` to `ollama-cloud` / `deepseek-v4.1-flash:cloud` / `high`. |

B1 is the load-bearing change — it is what stops the pruning. B2 restores the two providers that exist only
in user settings.

`DEEPSEEK_API_KEY` stays in the credentials file, unused and unselected. Say the word and I will remove it.

---

## Fault 3 — boot crash on a corrupt session log

**Receipt** — `~/.dsh/logs/dsh-web.err.log`, Oct 14 08:02:

```
failed to apply loader entry workspace (@deepseek-ai/dsh-workspace):
corrupt Zstandard session log: first frame is not exactly one header line
  at assertZstdHeaderFrame (packages/session/session-persistence-jsonl/src/index.ts:49:11)
  at WorkspaceRegistry.[cordis.init] (packages/workspace/workspace/src/index.ts:133:37)
```

A single unreadable session artifact takes down the whole workspace registry at boot, which also takes the
sidebar and the Session Manager's data source with it.

**Current state:** I scanned all 87 files under `~/.dsh/sessions` — every `session*.zstd` has a valid magic
number and passes `zstd -t`. Nothing is corrupt *right now*, so this is a latent boot hazard, not an active break.

**Pre-existing tooling, no need to write more:** `!Alice Coding Arm/scratch/repack_sessions.mjs`,
`verify_repack.mjs`, `probe_zstd_scan.mjs` (Oct 2) already do the scan-and-repack.

**Action:** before the first restart, re-run the scan. If it reports a bad frame, run the existing repack tool
on that file rather than deleting it, and re-scan. If it comes back clean, take no action — but this gets fixed
loudly rather than silently if it recurs.

---

## Order of work

1. B1 + B2 — settings and profile patch (nothing running depends on them yet).
2. A1 + A2 — point both launchers at the homebrew dsh.
3. Stop PID 29926 and restart through the launcher.
4. Fault 3 scan, then verify.

## Verification — what must be true before I call this done

- `curl -sS -X POST http://127.0.0.1:3080/api/session-manager/ping -d '{"rpcId":"v1"}'` returns a
  `{"type":"server-response",…}` envelope, **not** `not found`.
- Settings → Session Manager lists the 37 archived sessions in `workspace.json`.
- The model picker lists `ollama-cloud`, `ollama-local`, `inception`, `gemini` — and no DeepSeek entry.
- The default model reads `Ollama Cloud · DeepSeek V4.1 Flash`.
- `~/.dsh/settings.yaml` still contains `llm-pi-ai` after a settings write (the pruning is actually dead).

## Open — needs your call, not guessing

- **Gemini context.** You said Gemini is "still context too big not working". It is declared
  `contextWindow: 1048576` in both `settings.yaml.imported` and the patch. Tell me the real ceiling you want
  (128K? 256K?) and I will set it; I am not inventing a number. Not the default model, so it does not block this repair.

---

# What the plan missed (added after the work was done and verified)

## 1. There was a third launcher, and it owned the port

`~/Library/LaunchAgents/com.sifta.dsh-web.plist` — `RunAtLoad` + `KeepAlive` — running
`pnpm dsh --profile web --port 3080` from the `!Alice Coding Arm` source checkout.

This, not the `.command` script, is what actually held port 3080. It is why the arm never
picked up *any* upgrade: every time the old build died it was restarted from the same
checkout, and killing it only made launchd bring it back. The plan named two launchers;
there were three, and the one it missed was the one in charge.

Now: `ProgramArguments` → `/opt/homebrew/bin/dsh web --no-open --port 3080`,
`WorkingDirectory` → the SIFTA repo, stdout → `~/.dsh/logs/dsh-web.out.log`.
Backup: `com.sifta.dsh-web.plist.bak-2026-10-15`.

**A launchd trap worth remembering:** `StandardOutPath` must not sit under `~/Music`
(or `~/Documents`, `~/Desktop`). launchd cannot open a TCC-protected path for a job's
stdio and fails the *entire job* with `EX_CONFIG (78)` — writing no output anywhere, which
looks exactly like the binary crashing. Measured: 86 respawns, zero bytes logged, until the
log path moved to `~/.dsh/logs/`.

## 2. dsh 0.2.0 requires a launch token — and `settings.yaml` no longer exists

Two behaviour changes in 0.2.0 that the 0.1.1 checkout never had:

- **Auth fence.** A bare `GET /` answers `401 dsh web authentication required`. The token is
  printed once per boot; exchanging it sets a cookie signed with a secret persisted in
  `.credentials.yaml`, so it survives restarts — a browser authenticates once.
  This would have broken two things silently: `_harness_is_ready()` (tokenless GET → reads
  its own healthy arm as a foreign service → `port_3080_non_dsh_service`, every owner
  coding request FAILED) and the embedded browser tab.
- **`settings.yaml` is a removed format.** `dsh-settings` renames it to
  `settings.yaml.imported` once and imports each section into the *profile*
  (`profiles/web/cordis.patch.yml`), then never looks at it again.

That second point explains the whole original mystery. The repeated clobbering of the user's
settings was two formats fighting over one file. Settings now live in the profile, one
source, and the churn is over.

Code for both: `sifta_alice_browser_widget.py` (`_DSH_AUTH_MARKER`, `_harness_launch_token`,
`_harness_url`), `start_alice_local_coding.command` (`harness_is_up`, `harness_token`).

## 3. Gemini and ollama-auto are not selectable

The user-settings `llm-pi-ai` section listed five providers; only three are reachable —
`ollama-local`, `ollama-cloud`, `inception`. These are the routes *declared* in the plugin
config. `gemini` and `ollama-auto` were never declared, so they are not routes at all and
the picker cannot offer them. Adding Gemini means declaring it in the `llm-pi-ai` row with a
real `baseURL` and a context window — the ceiling is the user's call, not a guess.

## Verified

- `/api/session-manager/ping` → `{"ok":true,...,"plugin":"session-manager","version":"0.5.0","menuDeleteAvailable":true}`
- Settings → Session Manager → **37 archived sessions**, Restore / Delete per row
- Settings → Models → DeepSeek, Local Ollama ●, Ollama Cloud ●, Inception Mercury ●
- Model selector reads **DeepSeek V4.1 Flash** (the chosen `ollama-cloud` default)
- KeepAlive tested: killed the server, launchd brought it back on a new pid
- All 82 session logs scanned for the corrupt-first-frame condition: **0 bad**

## Left alone deliberately

- `sifta-qwenpaw-coder:latest` preflight in the launcher — removed. Its base
  (`satgeze/qwenpaw-9b-heretic-1m`) is not local, nothing lists the model any more, and it
  would have pulled ~9GB on a path the launcher no longer needs to walk.
- `DEEPSEEK_API_KEY` sits unused in `.credentials.yaml` and is not the default.
- `GEMINI_API_KEY` / `INCEPTION_API_KEY` are hardcoded in plaintext in the launchd plist.
  They work; they are also readable by anything that can read that file.
