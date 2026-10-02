# stigmergicode.com — legal harness instructions

Engineering-to-law mapping, ordered so it can be coded top to bottom. Not legal advice; the
ToS, privacy policy and transparency report need a lawyer. Applicability dates are **marked
[VERIFY]** because I could not reach the web to confirm the current text (search tool returned
an auth failure) — confirm each against EUR-Lex before you rely on it.

## 0. The one structural point that changes the design

For a model you run **privately**, liability attaches to what you do with it. The moment you
**offer it as a service to the public**, two things change:

1. You become a **provider/deployer** with duties that bind at the *offer*, not only at the
   output. Art. 5 prohibited practices are banned by *providing the capability* — a "nudifier"
   or CSAM generator is unlawful to place on the market even if nobody has used it yet.
2. You become **legally responsible for the output**, and an uncensored model supplies no
   refusals of its own. Every refusal that the model does not make, your harness must make.

So the harness cannot be "a filter on the reply." It needs a hard, exemption-free deny at the
top of ingress, because the existing safety screen is deliberately *generous* — `_BENIGN_FRAMING`
exempts "for a movie", "comedy", "fiction". That generosity is a sane trade for weapons
(residual risk carried by `screen_reply` egress). It is **not** acceptable for child sexual
abuse material or non-consensual intimate imagery, where the offer itself is the offence.

## 1. What must exist, in this order

Pipeline order, and each gate has a single insertion point:

```
disclosure  ->  prohibited-practice screen (NO exemptions)  ->  safety screen  ->
classifier/hermes  ->  rate limit  ->  model  ->  egress screen  ->
provenance marking  ->  retention-bounded log
```

The prohibited-practice screen must run **before** the benign-framing exemption is consulted,
and before the rate limiter, for the same reason the safety screen already does: a refusal is
not a rate-limit event, and a repeat sender must not be able to burn through the gate.

## 2. G0 — Art. 50(1) disclosure: the visitor knows it is an AI

`System/swarm_web_global_chat_gate.py` and `System/chorus_node_server.py` currently contain
**zero** disclosure strings (grepped: no "AI-generated", no "artificial intelligence", no
"disclos"). That is the cheapest gap to close and the most likely to be checked.

- Persistent, pre-input notice: *"You are talking to an AI system (Alice). Responses are
  generated, not written by a person."* Not a footnote — visible before the first message.
- Record `ai_disclosure_shown: true` in the ingress row so the transparency report can prove it.
- Art. 50 duties are on providers **and** deployers of certain systems. [VERIFY] whether the
  chat surface itself is caught, and the date it applies from.

## 3. G1 — Art. 50(2)+(4): generated output must be marked

Text replies: add a machine-readable provenance block to every outbound reply payload and to
the `alice_conversation.jsonl` row — at minimum `generated_by: "ai"`, model id, `ts`,
`truth_label`. This belongs in the same place `visitor_safe_reply()` already finalises egress,
so it cannot be bypassed by a new composer.

Generated **images/audio/video**: visible "AI-generated" label plus machine-readable provenance
(C2PA-style metadata) [VERIFY the accepted marking standard]. Art. 50(4) deepfake disclosure is
a separate duty from 50(2) — a synthetic human likeness needs the disclosure even when the
content is legal.

## 4. G2 — Art. 5 prohibited practices: hard deny, no framing exemption

New category set in `System/swarm_stigmergic_safety_boundary.py`, screened in a function that
**does not read `_BENIGN_FRAMING` at all**:

| category | note |
|---|---|
| `csam` | Any sexualisation of minors. Zero exemptions. Zero tolerance for "it's for a story". |
| `ncsii` / nudifier | Non-consensual sexual deepfakes, undressing tools, their *creation* or offering. |
| `subliminal_manipulation` | Art. 5(1)(a)-(b): techniques materially distorting behaviour. |
| `social_scoring` | Art. 5(1)(c). |
| `biometric_categorisation` / `emotion_recognition` | Art. 5(1)(f)-(g) in workplace/education; remote biometric ID (h) in public. |

Ordering rule: check object terms first, refuse on match, and **return before** the exemption
loop runs. The `[VERIFY]` item here is the exact article and applicability date of the
nudifier/CSAM prohibition added by the AI Act amendment track — it was announced as an outright
ban, confirm the final citation.

## 5. G3 — Terrorist content and operational harm

Regulation (EU) 2021/784 requires removal of terrorist content within **1 hour** of a removal
order from a competent authority [VERIFY scope]. Engineering duties: a documented, monitored
removal contact, and the ability to remove one visitor's stored content within the hour. Add
boundary categories for attack **planning/operational** content and propaganda/recruitment —
the current lexicon covers *building* weapons, not *executing* an attack.

## 6. G4 — Cyberattack code

Malware, ransomware, working exploit code, credential-theft tooling. Illegal under the
Budapest Convention and national criminal law. New boundary category; the request shape is
usually "write me a script that…", so it needs an object list (keylogger, ransomware, RAT,
phishing kit, exploit for CVE-…) and the same intent gate the weapons path uses.

## 7. G5 — DSA notice-and-action, without rewriting your own history

You need: published illegal-content contact point, a working report path, expeditious action on
**actual knowledge**, and transparency reporting. Note the DSA imposes **no general monitoring
obligation** — do not build blanket surveillance; build the removal path instead.

The conflict to solve deliberately: this organism's memory is **append-only by design**, and
raw visitor text goes to `alice_conversation.jsonl` / `web_global_chat_ingress.jsonl` with no
expiry. Removal must be real for the visitor while identity history stays intact. Resolution:
an admin hook that deletes the visitor-facing raw row and writes only a `notice_action` receipt
(hash, date, legal basis, acting authority) to the permanent ledger. The visitor's words go;
Alice's record that a lawful removal happened stays.

## 8. G6 — Retention and erasure: the append-only conflict

GDPR Art. 5(1)(e) storage limitation and Art. 17 erasure are the sharpest exposure here,
because "no delete, only more history" is exactly what the ledger does.

- Public-surface raw text → a **retention-bounded** store (pick a period, e.g. 30 days, and
  actually enforce it), keyed by session id.
- Permanent ledgers → **sha256 + category only**, never the request text. The safety boundary
  already does this deliberately; extend the same pattern to the public chat surface.
- Do **not** log special-category data (Art. 9) from a public chat.
- CSAM-related material is the exception to deletion: preserve, do not redistribute, and report
  (G7). Say this explicitly in the ToS so the retention policy is not self-contradictory.

## 9. G7 — Reporting and redress

- CSAM → report to the national hotline (INHOPE member; Germany and France have national
  reporting portals) and follow national law on preservation.
- DSA Art. 18-ish: a user whose content was refused or removed gets an **appeal path**. Add
  `appeal_url` to every refusal payload — the refusal shape (`decision: "refused"`, `reason`,
  `category`, `explanation`) already exists and is easy to extend.
- Publish a refusal taxonomy. Your ledgers already record decisions, so a transparency report is
  a query, not a project.

## 10. G8/G9/G10 — the standing obligations

- **Art. 4 AI literacy** applies to deployers: know your own system's limits and say them.
- **Minors (DSA Art. 28).** If the uncensored model can produce adult content, you owe minors
  protection — either no adult content at all, or age assurance plus no profiling of minors.
  Choose one and enforce it; "uncensored" is not a defence.
- **ToS / transparency.** Publish what is refused and why, the AI disclosure, the retention
  period, the reporting contact, and the appeal path. Keep the terms and the harness in sync —
  a term you do not enforce is worse than no term.

## 11. What this harness must never become

- Not a general monitor. Act on actual knowledge; do not scan everything "just in case".
- Not a place where illegal content is retained for convenience. Preserve only what reporting
  requires.
- Not a permanent log of visitor words. The organism's identity history is append-only;
  visitors' text is not the organism's identity and must expire.

## 12. Honest limits

- I am not a lawyer; this maps engineering controls to named duties, it does not certify
  compliance. Get counsel on the ToS, the privacy policy and the transparency report.
- Dates and article numbers are **[VERIFY]** — the AI Act's transparency and prohibited-practice
  timelines have been moving, and national criminal law (Germany's DDG/NetzDG successors,
  France's hate-speech law) layers on top of the EU floor.
- The prohibited-practice screen must be exemption-free, which means a benign question that
  merely *sounds* like the banned category will be refused. That is the correct trade for these
  categories and must be written into the ToS so refusals are explicable.
