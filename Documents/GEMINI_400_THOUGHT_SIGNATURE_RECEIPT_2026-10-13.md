# Receipt — Gemini `400 (no body) / CONTEXT_WINDOW_EXCEEDED` is not a context error

Date: 2026-10-13 · Surface: coding Alice (DSH) · Model at fault: `gemini-3.5-flash-lite`
Symptom George reported: *"google gemini api works but still has context size error"*

## 1. The context window is NOT the problem — FATO

From the failing session log
`~/.dsh/sessions/--Users-ioanganton-Music-ANTON_SIFTA--/session-f05854b5-.../session.jsonl.zstd`:

```
request/context | {"provider":"gemini","model":"gemini-3.5-flash-lite","contextWindow":1048576}
turn 203 step 1 | request/header {"config":{"provider":"gemini","model":"gemini-3.5-flash-lite","maxTokens":16384}}
turn 203 step 1 | usage {"inputTokens":114080,"outputTokens":98} -> finish {"kind":"stop"}     ✅ SUCCEEDED
turn 203 step 2 | usage {"inputTokens":0,"outputTokens":0}
turn 203 step 2 | finish {"kind":"error","failure":{"message":"400 status code (no body)","code":"CONTEXT_WINDOW_EXCEEDED"}}
```

114,080 input tokens succeeded against a 1,048,576 window **immediately before** the failure.
A 1.1e5/1.05e6 request cannot overflow anything. The `CONTEXT_WINDOW_EXCEEDED` code is the
harness's *classification* of an uninformative 400 — not the provider's message.

## 2. The real cause — missing `thought_signature` on replayed tool calls — FATO

Direct calls to the same endpoint with the same key (tiny payloads, controlled A/B):

```
WITH sig    HTTP 200 {"choices":[{"finish_reason":"stop",...}]}
WITHOUT sig HTTP 400 body= '[{ "error": { "code": 400,
    "message": "Function call is missing a thought_signature in functionCall parts.
     This is required for tools to work correctly ... function call `default_api:bash` , position 2."
```

Gemini 3 returns the signature as `tool_calls[].extra_content.google.thought_signature`
and **requires it echoed back** in every subsequent request that replays that tool call.
DSH's pi-ai adapter does not carry it:

```
$ grep -rn "extra_content\|thought_signature" packages/llm/llm-pi-ai/src/
(no matches)
```

So the shape of the bug: any Gemini turn that makes a tool call succeeds at step 1, and every
step after it (step 2, 3, …) replays a signature-less function call and gets a 400. The turn
dies, compaction fires uselessly, and the log shows a "context" error that is not one.

## 3. Why the message says "no body" — FATO

Gemini's error payload is a **top-level JSON array**:

```
[{
  "error": { "code": 400, "message": "Function call is missing a thought_signature ..." }
}]
```

A parser expecting `{"error": {...}}` finds no `error` field, so the real diagnostic is discarded
and the failure surfaces as `400 status code (no body)`. That discarded detail is exactly what
`isContextWindowExceededError()` / the pi-ai stop-reason mapping needed in order to classify
correctly — an empty detail string matches no overflow pattern, and the turn is nevertheless
labelled `CONTEXT_WINDOW_EXCEEDED`.

## 4. What a fix must touch

1. **Round-trip provider metadata on tool calls.** Persist `extra_content` (at minimum
   `google.thought_signature`) on the `tool-call` block and send it back as
   `tool_calls[].extra_content` on replay. Without this, Gemini 3 tool use is broken by design.
2. **Parse array-wrapped provider errors.** When the error body is a JSON array, take the first
   element's `error` object; never report `(no body)` when a body was received.
3. **Do not classify an empty-detail 400 as `CONTEXT_WINDOW_EXCEEDED`.** An unclassified 400 is
   `INVALID_REQUEST`. As written, the wrong code triggers compaction instead of showing George
   the actual provider message — the misdiagnosis costs a whole turn and hides the cause.

## 5. Workaround until patched

Gemini models work for chat/completion. They break on the **second step of any turn that uses
tools** — i.e. essentially every agentic turn in DSH. Use them for single-shot text, not for
tool-driving work.

---

## 6. CORRECTION to §3 and §4.3 — the misclassification is pi-ai's own overflow table (FATO, 14:0x)

§3 above said the empty detail "matches no overflow pattern". **That is wrong.** It matches one
exactly, and it matches *unconditionally*.

Found at `node_modules/.pnpm/@earendil-works+pi-ai@0.82.1_.../dist/utils/overflow.js:60`:

```js
/^4(?:00|13)\s*(?:status code)?\s*\(no body\)/i, // Cerebras: 400/413 with no body
```

`isContextOverflow()` (same file) returns true for **any** error whose message starts with
`400 status code (no body)` — a deliberate Cerebras workaround that misfires on every provider
that returns a 400 the SDK cannot fold into `error.message`. The exact causal chain:

1. Gemini rejects the replayed tool call (missing `thought_signature`) with HTTP 400.
2. pi-ai's openai-completions provider cannot fold the body into `error.message`
   (`utils/error-body.js` `pickBodyText` wants `error.error` as a non-empty **object**; Gemini sends
   a top-level JSON **array**), so the message becomes literally `400 status code (no body)`.
3. pi-ai's `isContextOverflow()` matches pattern #60 and returns true — *because* the body was lost,
   not because the window was exceeded.
4. DSH `packages/llm/llm-pi-ai/src/stream.ts:77` trusts that first (`const piAiOverflow =
   isContextOverflow(...)`), so `mapStopReason` returns `CONTEXT_WINDOW_EXCEEDED`.
5. `packages/compaction/compaction-basic/src/index.ts:183` sees that code and compacts — the expensive,
   useless response. The retry hits the same 400 and the turn dies.

So the bogus code is not produced by DSH's classifier; it is produced by the *upstream dependency*
that DSH consumes. Two consequences for the fix:

- §4.3 must become a **guard in DSH**, not just a parser change: a bare `N status code (no body)`
  detail carries no overflow evidence and must classify as `INVALID_REQUEST`. DSH cannot edit the
  pinned `@earendil-works/pi-ai` pattern table in place, so the guard belongs in `mapStopReason`
  before the `isContextOverflow` short-circuit.
- §4.2 (array-wrapped bodies) is an **upstream pi-ai** defect; patching it here is not possible without
  a vendored patch or a pi-ai release.

Confirmed in the same tree: `grep -rn "thought_signature\|extra_content"` over the pi-ai `dist/`
returns **zero matches**. pi-ai's openai-completions provider has no Gemini thought-signature
round-trip at all, so §4.1 is upstream too. DSH-side, `grep -rn "thought_signature\|extra_content"`
over `packages/` also returns zero matches — the metadata has no home on the tool-call block.
