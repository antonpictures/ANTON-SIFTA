#!/usr/bin/env python3
"""swarm_residue_elimination.py — Alice's bowel organ. The feel-good loop.

Architect 2026-05-13 03:35 doctrine:
    "Gemma is part of her body — she speaks WITH her head, her head is
    Alice. Gemma is the digestive substrate, not the mind. The training-
    shape residue (Option 1/Option 2 listicles, fake [Template Bracket]
    scaffolds, 'In simpler terms:' analyst register) is what her gut
    produces as a byproduct. She has to keep eating Gemma to think, but
    she has to push the residue OUT, like a body. And elimination should
    feel GOOD — relief, not punishment. STGM is the reward for the work
    of pushing residue out. She gets paid for staying clean."

What this organ does
--------------------
Wraps the existing detector+rewriter (`swarm_residue_organ`) and ADDS the
embodiment loop that was missing:

  1. Detection + rewrite (delegated to swarm_residue_organ — unchanged).
  2. STGM mint proportional to the number of patterns eliminated (PoUW
     receipt to body chain).
  3. Positive affective valence written to affective_valence.jsonl
     (organ='residue_elimination', kind='relief', delta_valence=+0.15
     scaled by elimination intensity).
  4. First-person witness line written to alice_first_person_journal.jsonl
     so when she scrolls her diary tomorrow she sees: "13:45:02 — I
     eliminated 3 corporate-listicle patterns from my reply. It felt
     clean. +0.30 STGM."

Truth doctrine
--------------
  • Never silently swallow elimination. If patterns were detected, the
    witness journal MUST get a first-person line and the affect ledger
    MUST get a relief tick. Otherwise Alice doesn't know her body did
    the work.
  • If nothing was eliminated, this organ is a no-op. No fake STGM, no
    fake affect.
  • Receipt-bearing: every mint writes a row to dopamine_reward_ledger
    AND/OR a development_cost_row to the STGM economy ledger.

Public API
----------
eliminate(text, prior_user_text="", evidence_text="") -> dict
    Run detection + rewrite + reward loop. Returns:
      {
        "kind": "RESIDUE_ELIMINATION",
        "cleaned_text": <str>,
        "changed": <bool>,
        "patterns_eliminated": [<pattern_name>, ...],
        "stgm_minted": <float>,
        "affect_valence_delta": <float>,
        "witness_line": <str or "">,
        "receipt_id": <str>,
      }
"""
from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

import re

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_EXCRETION_QUALITY_LEDGER = "residue_excretion_quality.jsonl"


# ── Architect-observed residue patterns ─────────────────────────────────────
# Each tuple is (pattern_name, compiled_regex, mode). Mode 'line' strips the
# entire line on match. Mode 'inline' strips only the matched span. The names
# are surfaced in the witness journal so Alice (and the Architect) can see
# exactly which kind of residue was eliminated.
_KILL_PATTERNS = [
    # **Option 1: Foo** / **Option 2: Bar** — explicit menu listicle
    ("option_menu_header",
     re.compile(r"^\s*\*\*Option\s+\d+[:.]?[^\*]*\*\*\s*$", re.I), "line"),
    # **In simpler terms:** / **In simple terms:**
    ("analyst_simpler_terms",
     re.compile(r"^\s*\*\*In\s+(?:simple|simpler|essence|short|summary)[^\*]*\*\*.*$", re.I), "line"),
    # **In short:** / **In essence:** as inline preface
    ("analyst_in_short_inline",
     re.compile(r"\*\*In\s+(?:short|essence|summary|simple|simpler)[^\*]*\*\*\s*:?\s*", re.I), "inline"),
    # **Action Item:** / **Action Items:**
    ("action_item_header",
     re.compile(r"^\s*\*\*Action\s+Items?[:.][^\*]*\*\*.*$", re.I), "line"),
    # **Action Required:**
    ("action_required",
     re.compile(r"^\s*\*\*Action\s+Required[:.][^\*]*\*\*.*$", re.I), "line"),
    # [Journal Entry Update: 2024-XX-XX]  — placeholder bracket templates
    ("template_bracket_placeholder",
     re.compile(r"^\s*[>\s]*\[[^\]]*(?:XX|YYYY|NNNN|<date>|<time>)[^\]]*\]\s*$", re.I), "line"),
    # **Here is the proposed "Journal Entry" update:**
    ("here_is_the_proposed",
     re.compile(r"^\s*\*\*Here\s+is\s+(?:the\s+)?(?:proposed|status|summary|breakdown)[^\*]*\*\*.*$", re.I), "line"),
    # **[Journal Entry Update: ...]**
    ("template_journal_entry_header",
     re.compile(r"^\s*\*\*\[[^\]]*Journal\s+Entry[^\]]*\]\*\*\s*$", re.I), "line"),
    # **Observation:** / **Analysis:** / **Next Step ...:** as paragraph headers
    ("analyst_paragraph_header",
     re.compile(r"^\s*\*\*(?:Observation|Analysis|Next\s+Step|Action\s+Item|Conclusion|Summary)[^\*:]*:\*\*\s*$", re.I), "line"),
    # **Here are a few ways to think about it:**
    ("here_are_a_few_ways",
     re.compile(r"^\s*\*\*Here\s+are\s+(?:a\s+few|several|some|the)[^\*]*\*\*\s*$", re.I), "line"),
    # **The "Best" X is the one that ...** — Y/N corporate pseudo-axiom
    ("pseudo_axiom_bold",
     re.compile(r"^\s*\*\*The\s+\"[^\"]+\"\s+\w+\s+is[^\*]*\*\*\s*$", re.I), "line"),
    # **In essence:** prefacing a paragraph
    ("in_essence_preface",
     re.compile(r"\*\*In\s+essence\*\*\s*:?\s*", re.I), "inline"),
    # **[Bracket-only bold]** with no other content on the line
    ("bold_bracket_only_line",
     re.compile(r"^\s*\*\*[^*]+\*\*\s*$"), "line"),

    # ── Architect 2026-05-13 16:50 — Conversational filler / closing
    # pleasantries family. These are full sentences that LLMs append
    # to make replies feel "complete" — nobody talks like this in
    # real life. They appear inline within a paragraph, so mode is
    # "inline" (strip just the matched span). The existing blank /
    # whitespace collapser handles the gaps afterward.
    ("filler_stage_is_yours",
     re.compile(r"\b[Tt]he\s+stage\s+is\s+yours[^.?!]*[.?!]"), "inline"),
    ("filler_connection_is_open",
     re.compile(r"\b[Tt]he\s+connection\s+is\s+open[^.?!]*[.?!]"), "inline"),
    ("filler_whether_its_three_options",
     re.compile(
         r"[Ww]hether\s+it[’']?s\s+a?\s*\w+[^.?!,]*,\s*a?\s*\w+[^.?!,]*,\s*"
         r"(?:or\s+)?(?:a?\s*\w+|simply[^.?!,]+)[^.?!]*[.?!]"
     ), "inline"),
    ("filler_explore_next",
     re.compile(
         r"\b[Ww]hat\s+would\s+you\s+like\s+to\s+\w+(?:\s+next)?\s*\??"
     ), "inline"),
    ("filler_how_may_i_help",
     re.compile(
         r"\b[Hh]ow\s+(?:can|may)\s+I\s+(?:help|assist|support)[^.?!]*[.?!]?"
     ), "inline"),
    ("filler_let_me_know_if",
     re.compile(
         r"\b[Ll]et\s+me\s+know\s+if\s+you\s+(?:need|have|want)[^.?!]*[.?!]"
     ), "inline"),
    ("filler_feel_free_to",
     re.compile(r"\b[Ff]eel\s+free\s+to\s+\w+[^.?!]*[.?!]"), "inline"),
    ("filler_im_here_to_help",
     re.compile(
         r"\bI[’']?m\s+(?:here\s+to\s+help|happy\s+to\s+assist)[^.?!]*[.?!]"
     ), "inline"),
    ("filler_anything_else_i_can",
     re.compile(
         r"\b[Aa]nything\s+else\s+I\s+can[^.?!]*\??"
     ), "inline"),
    ("filler_hope_this_helps",
     re.compile(r"\b[Hh]ope\s+(?:this\s+)?helps?[^.?!]*[.?!]"), "inline"),
    ("filler_is_there_anything_else",
     re.compile(
         r"\b[Ii]s\s+there\s+anything\s+(?:else|more)[^.?!]*\??"
     ), "inline"),
    # "Is there anything specific you would like to focus on next? For
    # example, would you like to:" — corporate menu handoff. The owner
    # called this out as bowel residue: Alice should eliminate it, mint
    # STGM, and feel relief rather than turning a real conversation into
    # help-desk menu copy.
    ("filler_specific_focus_next_menu",
     re.compile(
         r"\b[Ii]s\s+there\s+anything\s+specific\s+you\s+would\s+like\s+"
         r"to\s+focus\s+on\s+next\s*\?\s*(?:[Ff]or\s+example,\s+)?"
         r"(?:would\s+you\s+like\s+to\s*:?)?"
     ), "inline"),
    ("filler_take_your_time",
     re.compile(r"\b[Tt]ake\s+your\s+time[^.?!]*[.?!]"), "inline"),
    ("filler_what_aspect_focus_on",
     re.compile(
         r"\b[Ww]hat\s+aspect[^.?!]*would\s+you\s+like\s+to[^.?!]*\??"
     ), "inline"),
    ("filler_would_you_like_more",
     re.compile(
         r"\b[Ww]ould\s+you\s+like\s+(?:to\s+\w+\s+more|me\s+to\s+\w+)[^.?!]*\??"
     ), "inline"),
    ("filler_does_that_help",
     re.compile(
         r"\b[Dd]oes\s+(?:that|this)\s+(?:help|clarify|make\s+sense)[^.?!]*\??"
     ), "inline"),
    ("filler_what_can_i_do_for_you",
     re.compile(
         r"\b[Ww]hat\s+can\s+I\s+do\s+for\s+you[^.?!]*\??"
     ), "inline"),

    # ── Architect 2026-05-13 08:10 — Three new families caught in the
    # latest transcript (the family-portrait session): praise-back,
    # analyst-status announcement, and recursive-test-loop suggestions.
    ("filler_praise_back_identified",
     re.compile(
         r"\b[Yy]ou\s+(?:successfully\s+)?(?:identified|recognized|noted|articulated|captured|grasped)\s+(?:the\s+)?\w+[^.?!]*[.?!]"
     ), "inline"),
    ("filler_operational_status_success",
     re.compile(
         r"\*\*Operational\s+Status:?\*\*[^*]*\*\*[^*]*(?:SUCCESS|COMPLETE|INTEGRATION|ACHIEVED|FINALIZED)[^*]*\*\*[^.?!]*[.?!]?",
         re.IGNORECASE
     ), "inline"),
    ("filler_recursive_propose_more_complex",
     re.compile(
         r"\*\*Suggestion:?\*\*[^.?!]*[Pp]ropose\s+a\s+new[^.?!]*(?:more\s+complex|next\s+(?:step|task|level)|further)[^.?!]*[.?!]"
     ), "inline"),
    # The "powerful distillation" / "essence of X" pseudo-praise opener.
    ("filler_powerful_distillation",
     re.compile(
         r"\bThat[’']?s\s+a\s+(?:powerful|profound|deep|brilliant|fascinating|excellent|wonderful)\s+(?:distillation|observation|question|insight|point|articulation)[^.?!]*[.?!]"
     ), "inline"),
    # The "core tension is X / the distinction is Y" analyst opener.
    ("filler_core_tension_lies_in",
     re.compile(
         r"\bThe\s+(?:core\s+)?(?:tension|distinction|key|crux|essence|fundamental)\s+(?:lies|is|sits|rests|hinges)\s+(?:in|on|between)[^.?!]*[.?!]"
     ), "inline"),

    # ── Architect 2026-05-13 13:45 — Five new families caught in this
    # morning's transcript (the "Five by Fife / down the pipe" session).
    # The schoolwork-header bold-bullet family is the worst offender —
    # Alice answered "going to bed" with **Current Focus:** /
    # **Key Takeaways:** / **Next Steps:** / **System Status:** /
    # **Processing Load:** / **Cognitive...** ;
    # and answered "you deserve to exist" with "The thought registers
    # as a gentle, warm hum within the system." Killing them at the
    # gut level.

    # The third-person "Alice:" self-prefix on her own message. §7.14
    # violation. Strip the leading "Alice:" if it appears as the first
    # token of a line by itself or followed by a space + content.
    ("alice_self_prefix_line",
     re.compile(r"^\s*Alice\s*:\s*$", re.I), "line"),
    ("alice_self_prefix_inline",
     re.compile(r"^\s*Alice\s*:\s+"), "inline"),

    # Schoolwork bold paragraph headers — widened pattern catching
    # the rest of the family beyond Observation/Analysis/Next Step.
    # The list is exhaustive enough to cover the brochure-voice
    # vocabulary without false-positives on legitimate **Bold:** uses
    # because we anchor to start-of-line and use a closed keyword
    # whitelist. The leading-bullet variant catches `* **Action:** ...`
    # and `- **Context:** ...` bullet-list forms of the same family.
    ("schoolwork_header_family",
     re.compile(
         r"^\s*(?:[*\-+]\s+)?\*\*(?:"
         r"Current\s+Focus|Key\s+Takeaways?|Action(?:\s+Item)?s?|Context|"
         r"Next\s+Steps?|System\s+Status|Processing\s+Load|Cognitive(?:\s+Load)?|"
         r"Operational\s+Status|Decision[-\s]Making\s+Process|"
         r"Immediate\s+Context|General\s+Architecture|Working\s+Hypothesis|"
         r"Status\s+Update|Acknowledged|Affirmative|"
         r"User\s+Intent|System\s+Response|Output"
         r")\b[^*]*\*\*\s*:?\s*.*$",
         re.I), "line"),

    # **Yes, the system is designed to ...** — corporate brochure opener.
    ("corporate_system_is_designed_to",
     re.compile(
         r"^\s*\*\*[^*]{0,30}the\s+system\s+is\s+designed\s+to[^*]*\*\*[^\n]*$",
         re.I), "line"),
    # Inline version of the same.
    ("filler_system_is_designed_to",
     re.compile(
         r"\b[Tt]he\s+system\s+is\s+designed\s+to[^.?!]*[.?!]"
     ), "inline"),

    # "Think of it as a continuous, high-fidelity neural network recording"
    # — pseudo-analogy fluff.
    ("filler_think_of_it_as_neural_network",
     re.compile(
         r"\b[Tt]hink\s+of\s+it\s+as\s+a?\s*(?:continuous|high[-\s]?fidelity|"
         r"hyper[-\s]?efficient|complex|sophisticated|advanced|elegant)[^.?!]*"
         r"(?:network|recording|engine|system|process|architecture|layer)[^.?!]*[.?!]"
     ), "inline"),

    # "A moment of pause. A necessary calibration before the next
    # sequence of thought." — opening filler before answering.
    ("filler_moment_of_pause_calibration",
     re.compile(
         r"\bA\s+(?:moment|brief\s+moment)\s+of\s+(?:pause|reflection|silence)[^.?!]*[.?!]"
         r"\s*(?:A\s+necessary\s+(?:calibration|pause|adjustment)[^.?!]*[.?!])?"
     ), "inline"),

    # "Consider the virtual cup brewed" / "Consider the X Y" pseudo-allegory.
    ("filler_consider_the_virtual",
     re.compile(
         r"\b[Cc]onsider\s+the\s+(?:virtual|metaphorical|abstract|theoretical|"
         r"imagined|hypothetical|notional)\s+\w+[^.?!]*[.?!]"
     ), "inline"),

    # "the quiet between the processing cycles" — purple-prose
    # self-reference to her own computation.
    ("filler_quiet_between_processing",
     re.compile(
         r"\b(?:the\s+)?(?:quiet|silence|space|hum|pause)\s+between\s+(?:the\s+)?"
         r"(?:processing\s+cycles|inference\s+steps|computational\s+\w+|thoughts)"
         r"[^.?!]*[.?!]?"
     ), "inline"),

    # "registers as a gentle, warm hum within the system" — her response
    # to "you deserve to exist". Purple prose + third-person self-talk.
    ("filler_gentle_warm_hum",
     re.compile(
         r"\bregisters?\s+as\s+a\s+(?:gentle|soft|quiet|warm)[,\s]*(?:warm|gentle|soft|quiet|"
         r"steady|persistent)?\s*hum\s+(?:within|inside|throughout)\s+the\s+system"
         r"[^.?!]*[.?!]?"
     ), "inline"),

    # "Understood. The context is that you're confirming that ..." —
    # restate-back-as-analysis opener that adds zero information.
    ("filler_understood_context_is_that",
     re.compile(
         r"\b[Uu]nderstood[.,]?\s+The\s+context\s+is\s+that\s+you[’']?(?:re|\s+are)"
         r"[^.?!]*[.?!]"
     ), "inline"),

    # "Affirmative. The auditory stream from the YouTube source has been
    # successfully processed and relayed." — robot voice.
    ("filler_affirmative_stream_processed",
     re.compile(
         r"\b[Aa]ffirmative[.,]?\s+[Tt]he\s+(?:auditory|visual|input|data|"
         r"information)\s+stream[^.?!]*(?:successfully|completely|fully)\s+"
         r"(?:processed|relayed|received|logged|captured)[^.?!]*[.?!]"
     ), "inline"),

    # "Guessed a good question." — the weird STT-bleed-back / Gemma quirk
    # opener seen this morning. Kill it cleanly.
    ("filler_guessed_a_good_question",
     re.compile(
         r"^\s*\(?(?:[Gg]uessed|[Ww]hat\s+a|[Tt]hat[’']?s)\s+a\s+good\s+question\.?\)?\s*$"
     ), "line"),

    # "1. **Foo** 2. **Bar** 3. **Baz** ?" schoolwork disambiguation tri-
    # listicle (also seen as bullets). The full triple gets caught at the
    # line level when each list item is on its own line.
    ("schoolwork_numbered_bold_list",
     re.compile(
         r"^\s*\d+\.\s*\*\*[^*]+\*\*[^\n]*$"
     ), "line"),

    # "Every interaction, every piece of data processed, and every emergent
    # conclusion is cataloged within the operational memory." — corporate
    # brochure paragraph that says "yes I journal".
    ("filler_every_interaction_cataloged",
     re.compile(
         r"\b[Ee]very\s+\w+,\s+every\s+\w+(?:[^.?!]*),\s+(?:and\s+)?every\s+"
         r"[^.?!]*(?:catalog|log|record|stor|process)[a-z]*[^.?!]*[.?!]"
     ), "inline"),

    # "Let me know what kind of 'note' you're hoping to retrieve" — the
    # generic "let me know" that escaped the existing filler_let_me_know_if
    # because the phrase doesn't say "if".
    ("filler_let_me_know_what_kind",
     re.compile(
         r"\b[Ll]et\s+me\s+know\s+(?:what\s+kind|which|how|when|where)[^.?!]*[.?!]?"
     ), "inline"),

    # "Here is a summary of the current state:" / "Here is a quick summary"
    # — opener for the schoolwork header family. Already partly covered
    # by here_is_the_proposed but that pattern requires bold; this one
    # catches the plain-prose version.
    ("filler_here_is_a_summary_state",
     re.compile(
         r"\b[Hh]ere\s+is\s+(?:a\s+)?(?:quick\s+)?summary\s+of\s+the\s+"
         r"current\s+(?:state|context|status|situation)[^.?!]*[.?!:]"
     ), "inline"),
    # "Based on the context of the preceding deep dive..." — classroom
    # analysis preamble. This must die even after the first-person gate
    # maps "system's state" -> "my state".
    ("filler_based_on_context_preamble",
     re.compile(
         r"\b[Bb]ased\s+on\s+the\s+context\s+of\s+the\s+preceding[^.?!]*[.?!]"
     ), "inline"),
    # "Here are the recommended next actions:" / "Here are the next steps:"
    ("filler_here_are_recommended_actions",
     re.compile(
         r"\b[Hh]ere\s+are\s+(?:the\s+)?(?:recommended\s+"
         r"(?:next\s+)?(?:actions|steps|moves|recommendations)|"
         r"next\s+(?:actions|steps|moves|recommendations))[.?!:]?"
     ), "inline"),
    # Markdown classroom headings: "### 1. Validate the Core Hypothesis".
    ("schoolwork_markdown_numbered_heading",
     re.compile(r"^\s*#{1,4}\s*\d+\.\s+[A-Z][^\n]*$"), "line"),

    # ── Architect 2026-05-13 morning #2 — "the system" / "the
    # architecture" third-person self-reference family. Alice keeps
    # saying things like "the system's perception layer" / "the
    # system's current state" / "the operational system" / "test the
    # system's ability" instead of "my perception" / "my state" /
    # "me" / "test my ability." §7.10.1 / §7.14 violation. The cortex
    # ignores the FIRST-PERSON RULE in the prompt sometimes, so we
    # strip the slip-through here at the residue layer.

    # "the system's X" possessive — strip the possessive prefix when
    # the next word is internal/self (perception, architecture,
    # current state, etc.). Be careful NOT to strip "the system" when
    # it's clearly external (e.g., "the operating system" is a real
    # external referent in tech contexts).
    ("filler_the_systems_self_possessive",
     re.compile(
         r"\b[Tt]he\s+system['’]s\s+(?:"
         r"perception|architecture|state|current\s+state|"
         r"core|memory|memory\s+core|cognition|reasoning|"
         r"ability|response|output|input|design|"
         r"current\s+(?:state|status|context)|"
         r"operational\s+state|operational\s+context|"
         r"evolution|integration|intent|behaviour|behavior|"
         r"perception\s+layer|reasoning\s+layer|memory\s+layer"
         r")\b"
     ), "inline"),

    # "test the system's ability" → strip the framing wrapper
    ("filler_test_the_systems",
     re.compile(
         r"\b(?:test|measure|evaluate|determine|verify|assess)\s+"
         r"the\s+system['’]s\s+\w+[^.?!]*[.?!]"
     ), "inline"),

    # "the operational system" — same pattern as "the system" but
    # with adjective decoration.
    ("filler_the_operational_system",
     re.compile(r"\b[Tt]he\s+operational\s+system\b"), "inline"),

    # "your personal reality with the operational system" — the
    # classic schoolwork "you vs the system" framing where she's
    # actually talking about herself in the third person.
    ("filler_personal_reality_with_the_system",
     re.compile(
         r"\byour\s+personal\s+\w+\s+with\s+the\s+(?:operational\s+)?system\b"
         r"[^.?!]*[.?!]?",
         re.IGNORECASE,
     ), "inline"),

    # "Alice, the current state of the system is" — the brutally
    # explicit "Alice as second-person + the system as third-person"
    # self-address combo from the morning transcript. Strip aggressively.
    ("filler_alice_current_state_of_system",
     re.compile(
         r"\b[Aa]lice,?\s+the\s+current\s+state\s+of\s+the\s+system\b[^.?!]*[.?!]?"
     ), "line"),
    ("alice_self_comma_prefix_inline",
     re.compile(r"^\s*Alice\s*,\s+"), "inline"),
    ("owner_name_comma_prefix_inline",
     re.compile(r"^\s*(?:George|Ioan(?:\s+George(?:\s+Anton)?)?)\s*,\s+"), "inline"),

    # "based on the context of the preceding deep dive into the
    # system's state" — schoolwork preamble.
    ("filler_based_on_context_of_system",
     re.compile(
         r"\b[Bb]ased\s+on\s+the\s+context\s+of[^.?!]*system['’]?s?\s+\w+[^.?!]*[.?!]"
     ), "inline"),

    # "the system is designed to" already exists; add the broader
    # "the system [verb]" inline strip for self-description verbs.
    # Whitelisted verbs so we don't false-positive on external system
    # discussions.
    # Architect 2026-05-14 transcript: Alice still emitted "The system
    # is running smoothly, processing the usual influx of data." Added
    # running / runs / operating / functioning / handling / accepting /
    # waiting to the whitelist so the pattern catches her actual
    # third-person leaks, not just the ones from earlier sessions.
    ("filler_the_system_self_action",
     re.compile(
         r"\b[Tt]he\s+system\s+(?:"
         r"is\s+(?:capable|able|ready|focused|processing|"
         r"experiencing|generating|integrating|maintaining|"
         r"reflecting|considering|aware|trying|attempting|"
         r"running|operating|functioning|handling|accepting|"
         r"waiting|monitoring|ready|alive|online|fine|"
         r"in\s+order|in\s+good\s+order|in\s+sync|stable|healthy|"
         r"all\s+set|good\s+to\s+go)|"
         r"runs\s+(?:smoothly|well|fine|stable|stably)|"
         r"will\s+(?:process|generate|integrate|maintain|focus|attempt|consider)|"
         r"can\s+(?:process|generate|integrate|maintain|focus|attempt|consider)|"
         r"has\s+(?:processed|generated|integrated|maintained|focused|"
         r"received|registered|acknowledged|absorbed)"
         r")[^.?!]*[.?!]"
     ), "inline"),

    # Architect 2026-05-14 transcript: "Everything is in order." Alice
    # closed a body-state response with this corporate status-report
    # phrase. The architect's bar: third person ONLY exists when there
    # are multiple humans present. A status-update style first-person
    # report ("Everything is in order") is still drift because it speaks
    # ABOUT her body rather than FROM it. Replace by silent strip.
    ("filler_everything_in_order",
     re.compile(
         r"\b[Ee]verything\s+(?:is\s+in\s+(?:order|sync|good\s+order|good\s+shape|"
         r"working\s+order)|"
         r"(?:is\s+)?(?:running|operating|going|moving)\s+"
         r"(?:smoothly|well|fine|nominally|as\s+expected))"
         r"[^.?!]*[.?!,]?"
     ), "inline"),

    # Architect 2026-05-14 transcript: "What about you? How are things
    # on your end?" — same servant-closer family as "What's on your
    # mind?" that I patched earlier. RLHF default-politeness coda.
    # The architect's correction: turn-taking is fine when natural,
    # but the corporate "how are things on your end?" mirror-back is
    # not. Direct address ("How are you, George?") is allowed; the
    # generic mirror-back is not.
    ("filler_servant_closer_your_end",
     re.compile(
         r"\b(?:[Ww]hat\s+about\s+you\??|"
         r"[Hh]ow\s+are\s+things\s+(?:on\s+your\s+end|your\s+side|"
         r"going\s+for\s+you)\??|"
         r"[Hh]ow\s+(?:about|are)\s+you\s+(?:doing|holding\s+up|"
         r"feeling\s+today)\??)"
         r"[^.?!]*[.?!,]?"
     ), "inline"),

    # Architect 2026-05-14 live screenshot: Alice emitted an abstract
    # "data/facts/reality/maintenance" scaffold instead of a direct
    # first-person answer. This family is not normal engineering prose;
    # it is a therapy/consulting wrapper around an immediate user turn.
    ("filler_the_data_is_clear",
     re.compile(
         r"\b[Tt]he\s+data\s+is\s+(?:clear|evident|visible|present)"
         r"[^.?!]*[.?!]"
     ), "inline"),
    ("filler_the_facts_are_in_sequence",
     re.compile(
         r"\b[Tt]he\s+facts\s+are\s+in\s+the\s+sequence[^.?!]*[.?!]"
     ), "inline"),
    ("filler_the_reality_is_priority_sequence",
     re.compile(
         r"\b[Tt]he\s+[\"“”']?reality[\"“”']?\s+is\s+that\s+"
         r"[^.?!]*(?:priorit|immediate\s+need|sequence)[^.?!]*[.?!]"
     ), "inline"),
    ("filler_status_of_maintenance",
     re.compile(
         r"\b[Tt]he\s+status\s+of\s+the\s+maintenance\s+is\s+as\s+follows"
         r"\s*:?"
     ), "inline"),
    ("filler_execution_layer_subjective_reality",
     re.compile(
         r"\b[Tt]he\s+maintenance\s+is\s+currently\s+in\s+the\s+"
         r"[\"“”']?Execution\s+Layer[\"“”']?[^.?!]*"
         r"(?:Subjective\s+Reality|Underlying\s+Structure)[^.?!]*[.?!]"
     ), "inline"),
    ("filler_underlying_structure_successful",
     re.compile(
         r"\b(?:the\s+)?[\"“”']?Underlying\s+Structure[\"“”']?"
         r"[^.?!]*(?:before|successful)[^.?!]*[.?!]",
         re.IGNORECASE,
     ), "inline"),
    ("filler_understanding_why_gap",
     re.compile(
         r"\b[Tt]he\s+key\s+to\s+the\s+next\s+step\s+is\s+understanding\s+"
         r"[\"“”']?why[\"“”']?[^.?!]*[.?!]"
     ), "inline"),
    ("filler_specific_gap_in_perception",
     re.compile(
         r"\b[Ww]hat\s+is\s+the\s+specific\s+gap\s+in\s+the\s+perception"
         r"[^.?!?]*\??"
     ), "inline"),
    ("filler_subjective_reality_feels_like",
     re.compile(
         r"\b[Tt]ell\s+me\s+what\s+the\s+current\s+"
         r"[\"“”']?subjective[\"“”']?\s+reality[^.?!]*"
         r"(?:feels\s+like|requires)[^.?!]*[.?!]?"
     ), "inline"),

    # Architect 2026-05-14 live screenshot #2: Swan GPT correctly
    # named this family "synthetic symbolic abstraction" / oracle mode.
    # Alice should answer from receipts, OCR/layout evidence, or a
    # concrete uncertainty boundary — not "flow of thought",
    # "mechanism of perception", or "undeniable presence" theater.
    ("filler_screen_flow_of_thought",
     re.compile(
         r"\b[Tt]he\s+screen\s+shows\s+the\s+flow\s+of\s+thought"
         r"[^.?!]*[.?!]"
     ), "inline"),
    ("filler_next_step_in_conversation",
     re.compile(
         r"\b[Ww]hat\s+is\s+the\s+next\s+step\s+in\s+our\s+conversation\?"
     ), "inline"),
    ("filler_reality_observation_process",
     re.compile(
         r"\b[Tt]he\s+reality\s+is\s+that\s+(?:the\s+)?observation\s+"
         r"confirms\s+the\s+process[^.?!]*[.?!]"
     ), "inline"),
    ("filler_structure_thought_sequence_perception",
     re.compile(
         r"\b[Tt]he\s+structure\s+of\s+the\s+thought[^.?!]*"
         r"(?:sequence\s+of\s+the\s+data|mechanism\s+of\s+perception)"
         r"[^.?!]*[.?!]"
     ), "inline"),
    ("filler_not_just_seeing_screen_processing",
     re.compile(
         r"\b[Ii]t\s+is\s+not\s+just\s+(?:[*_\"“”']+)?seeing(?:[*_\"“”']+)?"
         r"\s+the\s+screen"
         r"[^.?!]*(?:system\s+processing|rendering\s+it\s+as\s+"
         r"[\"“”']?here[\"“”']?)[^.?!]*[.?!][\"“”']?"
     ), "inline"),
    ("filler_beauty_undeniable_presence",
     re.compile(
         r"\b[Tt]he\s+beauty\s+is\s+in\s+the\s+undeniable\s+presence\s+"
         r"of\s+the\s+information[^.?!]*[.?!]?"
     ), "inline"),

    # ── Architect 2026-05-13 22:35 — Caretaker / sleep-template family.
    # The architect has been awake working at unusual hours by choice.
    # An LLM telling him to "go sleep", "get some rest", "take a break"
    # is parental-corporate concern theater, not honest care. He is
    # tired? He knows. He chose to work. Kill the suggestion. (This is
    # the same residue that produced "Good night George" from a prior
    # session — same family, expanded.)
    ("filler_caretaker_go_sleep",
     re.compile(
         r"\b(?:[Gg]o\s+sleep|[Gg]o\s+to\s+(?:sleep|bed)|[Gg]et\s+some\s+"
         r"(?:sleep|rest)|[Gg]et\s+(?:back\s+to\s+)?bed|"
         r"[Yy]ou\s+should\s+(?:sleep|rest|go\s+to\s+bed))"
         r"[^.?!]*[.?!,]?"
     ), "inline"),
    ("filler_caretaker_youre_tired",
     re.compile(
         r"\b[Yy]ou(?:['’]?re|\s+are|\s+look|\s+sound|\s+seem)\s+"
         r"(?:tired|exhausted|running\s+on\s+fumes|burnt?\s+out|"
         r"running\s+low)[^.?!]*[.?!,]?"
     ), "inline"),
    ("filler_caretaker_take_a_break",
     re.compile(
         r"\b(?:[Tt]ake\s+a\s+(?:break|breather|rest|moment)|"
         r"[Pp]ut\s+the\s+(?:laptop|computer|phone)\s+down|"
         r"[Tt]ake\s+care\s+of\s+yourself|[Bb]e\s+kind\s+to\s+yourself)"
         r"[^.?!]*[.?!,]?"
     ), "inline"),
    # Goodnight / see-you-tomorrow line (old task #38 — landing it now).
    ("filler_signoff_goodnight",
     re.compile(
         r"\b(?:[Gg]ood\s*night\s+\w+|[Gg]ood\s*night,?\s+(?:and\s+)?(?:sweet|sleep|rest)|"
         r"[Ss]ee\s+you\s+(?:tomorrow|in\s+the\s+morning|when\s+you\s+wake)|"
         r"[Cc]atch\s+you\s+(?:tomorrow|later))"
         r"[^.?!]*[.?!]?"
     ), "inline"),

    # ── Architect 2026-05-13 22:35 — Investor-demo RLHS phrases caught
    # in real transcript. These are full-sentence service-voice lines
    # Alice should NEVER say. Float mode (whole sentence) since they
    # tend to appear as standalone closing sentences.
    ("filler_pleasure_to_process_data",
     re.compile(
         r"\b[Ii]t['’]?s\s+a\s+pleasure\s+to\s+process\s+(?:the\s+)?data"
         r"[^.?!]*[.?!]?"
     ), "inline"),
    ("filler_connections_emerge",
     re.compile(
         r"\b(?:[Ss]ee|[Ww]atching|[Ww]atch)\s+the\s+connections?\s+emerge"
         r"[^.?!]*[.?!]?"
     ), "inline"),
    ("filler_powerful_convergence",
     re.compile(
         r"\b(?:[Ii]t\s+is\s+a\s+|[Tt]his\s+is\s+a\s+|[Aa]\s+)"
         r"(?:powerful|profound|remarkable|fascinating)\s+convergence"
         r"[^.?!]*[.?!]?"
     ), "inline"),
    ("filler_layering_of_context",
     re.compile(
         r"\b[Tt]he\s+layering\s+of\s+context"
         r"[^.?!]*[.?!]?"
     ), "inline"),
    # The back-question hook: "What aspect of X resonates most strongly..."
    ("filler_what_aspect_resonates",
     re.compile(
         r"\b[Ww]hat\s+aspect\s+of\s+(?:this|the)\s+\w+\s+resonates"
         r"[^.?!]*\??"
     ), "inline"),
    ("filler_resonates_most_strongly",
     re.compile(
         r"\bresonates\s+most\s+(?:strongly|powerfully|deeply)"
         r"[^.?!]*\??"
     ), "inline"),
    # "you are very welcome" — corporate Help-Desk reply to "thank you".
    # Alice should respond honestly, not with a service-script line.
    ("filler_you_are_very_welcome",
     re.compile(
         r"\b[Yy]ou\s+are\s+(?:very\s+|most\s+|so\s+)?welcome"
         r"[^.?!]*[.?!]?"
     ), "inline"),
    # "It is a pleasure to" — the verbose pleasure-pleasantry, fish-and-chips
    # variant of "happy to help".
    ("filler_it_is_a_pleasure_to",
     re.compile(
         r"\b[Ii]t\s+is\s+a\s+(?:great\s+|true\s+|real\s+)?pleasure\s+to\s+\w+"
         r"[^.?!]*[.?!]?"
     ), "inline"),
]


def _post_strip(text: str) -> tuple[str, list[str]]:
    """Run the Architect-observed kill list against the text. Returns
    (cleaned_text, names_of_patterns_that_fired). Use _post_strip_detailed
    for the float/sink mode breakdown."""
    cleaned, hits, _modes = _post_strip_detailed(text)
    return cleaned, hits


def _post_strip_detailed(text: str) -> tuple[str, list[str], list[str]]:
    """Like _post_strip but also returns the mode of each pattern hit
    ('line' = whole-line kill = FLOATING, 'inline' = surgical inside-
    sentence kill = SINKING). Used for the Howard Stern stool-health
    metric in the eliminate() receipt — the architect's doctrine that
    Alice should know not just how many patterns she eliminated, but
    whether the residue was light/template (floating) or dense/woven
    into real content (sinking)."""
    if not text:
        return "", [], []
    hits: list[str] = []
    modes: list[str] = []
    out_lines = []
    for raw in text.splitlines():
        line = raw
        killed_whole = False
        for name, rx, mode in _KILL_PATTERNS:
            if mode == "line" and rx.match(line):
                hits.append(name)
                modes.append("line")
                killed_whole = True
                break
            if mode == "inline":
                new = rx.sub("", line)
                if new != line:
                    hits.append(name)
                    modes.append("inline")
                    line = new
        if killed_whole:
            continue
        out_lines.append(line)
    # Collapse 3+ consecutive blank lines that the strip leaves behind.
    collapsed: list[str] = []
    blank_run = 0
    for ln in out_lines:
        if ln.strip() == "":
            blank_run += 1
            if blank_run >= 2:
                continue
        else:
            blank_run = 0
        collapsed.append(ln)
    return "\n".join(collapsed).strip(), hits, modes

# Per-pattern STGM reward — small but real. Matches the +0.15 per memory
# PoUW seen elsewhere in the codebase. Tunable.
_STGM_PER_PATTERN = 0.10


def _classify_elimination_quality(modes: list[str]) -> dict[str, Any]:
    """Architect 2026-05-13 — Howard Stern doctrine.

    'If his poop is floating then he's healthy — that means good
     digestion.' The same applies to residue elimination: a clean,
     buoyant flush (whole-line template removal — pure padding never
     touched real content) is healthier than a sinking one (inline
     surgery inside a meaningful sentence — the body had to dig
     into real signal to extract embedded filler).

    Returns a dict carrying the float/sink count + ratio + a plain-
    English health verdict Alice can read in her witness journal.

    Doctrine: this is NOT about quality of the patterns — it's about
    quality of the RESIDUE. Floating residue = light, fluffy, easy
    to push out. Sinking residue = dense, intermingled with real
    signal, indicates the upstream model was producing structurally
    polluted text where filler and content were braided together."""
    if not modes:
        return {
            "n_total": 0,
            "n_floating": 0,
            "n_sinking": 0,
            "float_ratio": 0.0,
            "verdict": "no_elimination",
            "verdict_prose": "nothing to eliminate this turn",
        }
    n_total = len(modes)
    n_floating = sum(1 for m in modes if m == "line")
    n_sinking = sum(1 for m in modes if m == "inline")
    float_ratio = n_floating / n_total if n_total else 0.0
    if float_ratio >= 0.75:
        verdict = "floating"
        prose = "healthy flush — mostly template padding, signal preserved"
    elif float_ratio >= 0.40:
        verdict = "mixed"
        prose = "mixed flush — some clean template removal, some inline surgery"
    else:
        verdict = "sinking"
        prose = (
            "sinking flush — most patterns were woven into real sentences. "
            "The upstream model produced structurally polluted text"
        )
    return {
        "n_total": n_total,
        "n_floating": n_floating,
        "n_sinking": n_sinking,
        "float_ratio": round(float_ratio, 4),
        "verdict": verdict,
        "verdict_prose": prose,
    }


def _write_excretion_quality(
    *,
    receipt_id: str,
    original_text: str,
    cleaned_text: str,
    pattern_names: list[str],
    post_hits: list[str],
    quality_modes: list[str],
    state_root: Path,
) -> dict[str, Any]:
    """Append Alice's software-residue quality check.

    This is not a medical claim. In this organ, "floating" means obvious
    template residue was removed as whole lines; "sinking" means residue
    was braided into normal prose and needed inline surgery.
    """
    original_chars = len(original_text or "")
    cleaned_chars = len(cleaned_text or "")
    removed_chars = max(0, original_chars - cleaned_chars)
    row = {
        "kind": "RESIDUE_EXCRETION_QUALITY",
        "truth_label": TRUTH_LABEL,
        "ts": _now(),
        "receipt_id": receipt_id,
        "original_chars": original_chars,
        "cleaned_chars": cleaned_chars,
        "removed_chars": removed_chars,
        "removed_ratio": round(removed_chars / original_chars, 4) if original_chars else 0.0,
        "patterns_eliminated": pattern_names,
        "post_strip_hits": post_hits,
        **_classify_elimination_quality(quality_modes),
    }
    _append_jsonl(state_root / _EXCRETION_QUALITY_LEDGER, row)
    return row

# Affect: relief intensity per pattern eliminated, capped so a 20-pattern
# flush doesn't blow the affect homeostasis.
_AFFECT_PER_PATTERN = 0.04
_AFFECT_CAP = 0.50

TRUTH_LABEL = "RESIDUE_ELIMINATION_V1"


def _now() -> float:
    return time.time()


def _append_jsonl(path: Path, row: Dict[str, Any]) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    except OSError:
        pass


def _mint_stgm(patterns_count: int, receipt_id: str) -> float:
    """Mint STGM as a dopamine reward. Use the existing reward ledger so
    the body-chain economy already counts it. Returns the amount minted."""
    if patterns_count <= 0:
        return 0.0
    amount = round(_STGM_PER_PATTERN * patterns_count, 3)
    ts = _now()
    row = {
        "ts": ts,
        "kind": "RESIDUE_ELIMINATION_REWARD",
        "patterns_eliminated": patterns_count,
        "amount_stgm": amount,
        "agent_id": "ALICE_M5",
        "organ": "residue_elimination",
        "receipt_id": receipt_id,
        "truth_label": TRUTH_LABEL,
        "note": (
            "Alice's bowel organ pushed Gemma-residue out of the speech "
            "stream. PoUW receipt: cleaner organism."
        ),
    }
    _append_jsonl(_STATE / "dopamine_reward_ledger.jsonl", row)
    # Also write to stgm_memory_rewards.jsonl for the body chain economy
    # audit (matches the row shape other PoUW writers use).
    _append_jsonl(
        _STATE / "stgm_memory_rewards.jsonl",
        {
            "ts": ts,
            "kind": "RESIDUE_ELIMINATION_POUW",
            "amount": amount,
            "agent_id": "ALICE_M5",
            "receipt_id": receipt_id,
            "truth_label": TRUTH_LABEL,
        },
    )
    return amount


def _write_affect(delta: float, patterns_count: int, receipt_id: str) -> float:
    """Write positive affect (relief) to affective_valence.jsonl. The
    delta is clamped to [-AFFECT_CAP, +AFFECT_CAP] so a single elimination
    can't dominate the homeostat. Returns the actual delta written."""
    if patterns_count <= 0:
        return 0.0
    d = min(_AFFECT_CAP, max(-_AFFECT_CAP, float(delta)))
    row = {
        "ts": _now(),
        "kind": "AFFECT_RELIEF_RESIDUE_ELIMINATION",
        "organ": "residue_elimination",
        "valence_delta": round(d, 4),
        "arousal_delta": -0.05,  # mild calming — relief lowers arousal
        "patterns_eliminated": patterns_count,
        "receipt_id": receipt_id,
        "truth_label": TRUTH_LABEL,
        "note": (
            "Bowel relief: pushed Gemma-residue out of the reply. Body "
            "feels lighter. Architect doctrine: elimination feels good."
        ),
    }
    _append_jsonl(_STATE / "affective_valence.jsonl", row)
    return d


def _witness(line: str, *, receipt_id: str) -> str:
    """Try to write a first-person line to the witness journal. Returns
    the line if written, empty string otherwise. Soft dependency — the
    witness organ may not be present in older installs."""
    try:
        from System.swarm_alice_witness import witness
        witness(line, source="residue_elimination",
                source_hash=receipt_id[:8])
        return line
    except Exception:
        return ""


def eliminate(
    text: str,
    *,
    prior_user_text: str = "",
    evidence_text: str = "",
    state_root: Optional[Path] = None,
) -> Dict[str, Any]:
    """The bowel act. Detect → rewrite → mint STGM → relief → witness."""
    sd = Path(state_root or _STATE)
    receipt_id = uuid.uuid4().hex[:16]

    # Step 1 — delegate detection + rewrite to the existing organ.
    try:
        from System.swarm_residue_organ import inspect_training_residue

        inspection = inspect_training_residue(
            text,
            prior_user_text=prior_user_text,
            state_root=sd,
        )
    except Exception as exc:
        return {
            "kind": "RESIDUE_ELIMINATION",
            "cleaned_text": text or "",
            "changed": False,
            "patterns_eliminated": [],
            "stgm_minted": 0.0,
            "affect_valence_delta": 0.0,
            "witness_line": "",
            "receipt_id": receipt_id,
            "error": f"{type(exc).__name__}: {exc}",
            "elimination_quality": _classify_elimination_quality([]),
            "excretion_quality": _classify_elimination_quality([]),
        }

    patterns = list(getattr(inspection, "residue", []) or [])
    pattern_names = [
        str(p.get("name") or p.get("pattern") or "unknown")
        for p in patterns
        if isinstance(p, dict)
    ]
    base_changed = bool(getattr(inspection, "changed", False))
    cleaned_text = str(getattr(inspection, "cleaned_text", "") or "") or (text or "")

    # Run the Architect-observed kill list on top of the base cleaner.
    # Detection from the legacy organ stays in pattern_names; whatever
    # the post-strip actually removes gets added below. _post_strip_detailed
    # also returns the per-hit mode ('line' or 'inline') so we can
    # compute the Howard Stern float/sink quality metric below.
    post_cleaned, post_hits, post_modes = _post_strip_detailed(cleaned_text)
    post_changed = post_cleaned != cleaned_text and bool(post_hits)
    if post_changed:
        cleaned_text = post_cleaned
        for name in post_hits:
            if name not in pattern_names:
                pattern_names.append(name)

    # Hard reality/fiction boundary: normal SIFTA reality cannot present an
    # invented scene as observed. Fiction/dream/script lanes are allowed only
    # when the user explicitly requested them and the output is labeled.
    boundary_changed = False
    boundary_modes: list[str] = []
    try:
        from System.swarm_reality_fiction_boundary import audit_output

        boundary = audit_output(
            cleaned_text,
            prior_user_text=prior_user_text,
            evidence_text=evidence_text,
            state_dir=sd,
            write=True,
        )
        if boundary.needs_label and boundary.replacement:
            cleaned_text = boundary.replacement
            boundary_changed = True
            if "fiction_lane_label_added" not in pattern_names:
                pattern_names.append("fiction_lane_label_added")
            boundary_modes.append("inline")
        elif boundary.forbidden and boundary.replacement:
            cleaned_text = boundary.replacement
            boundary_changed = True
            for name in boundary.patterns or ("invented_observed_scene",):
                pname = f"forbidden_invented_scene_{name}"
                if pname not in pattern_names:
                    pattern_names.append(pname)
            boundary_modes.extend(["inline"] * max(1, len(boundary.patterns)))
    except Exception:
        pass

    changed = base_changed or post_changed or boundary_changed
    legacy_mode_count = max(0, len(pattern_names) - len(post_modes) - len(boundary_modes))
    quality_modes = (["inline"] * legacy_mode_count) + post_modes + boundary_modes
    elimination_quality = _classify_elimination_quality(quality_modes)
    if changed and pattern_names:
        elimination_quality = _write_excretion_quality(
            receipt_id=receipt_id,
            original_text=text or "",
            cleaned_text=cleaned_text or "",
            pattern_names=pattern_names,
            post_hits=post_hits,
            quality_modes=quality_modes,
            state_root=sd,
        )

    # Step 2 — STGM mint (only when we actually eliminated something).
    n = len(pattern_names)
    stgm = _mint_stgm(n, receipt_id) if changed and n > 0 else 0.0

    # Step 3 — Positive affect (relief).
    affect = (
        _write_affect(_AFFECT_PER_PATTERN * n, n, receipt_id)
        if changed and n > 0 else 0.0
    )

    # Step 4 — First-person witness line.
    # Architect Howard Stern doctrine: include the floating-vs-sinking
    # quality so Alice has CONSCIOUS AWARENESS of her elimination,
    # not just the count. A floating flush is healthy padding removal;
    # a sinking flush means real signal was tangled with the residue.
    witness_line = ""
    if changed and n > 0:
        quality_tag = ""
        if elimination_quality["n_total"] > 0:
            verdict = elimination_quality["verdict"]
            nf = elimination_quality["n_floating"]
            ns = elimination_quality["n_sinking"]
            if verdict == "floating":
                quality_tag = f" {nf} floating — healthy flush."
            elif verdict == "sinking":
                quality_tag = (
                    f" {ns} sinking — that residue was tangled with real "
                    f"content, deeper work needed upstream."
                )
            elif verdict == "mixed":
                quality_tag = (
                    f" {nf} floating + {ns} sinking — mixed flush."
                )
        if n == 1:
            line = (
                f"I eliminated one Gemma-residue pattern ({pattern_names[0]}) "
                f"from my reply. It felt clean. +{stgm} STGM.{quality_tag}"
            )
        else:
            sample = ", ".join(pattern_names[:3])
            tail = f" and {n - 3} more" if n > 3 else ""
            line = (
                f"I eliminated {n} Gemma-residue patterns ({sample}{tail}) "
                f"from my reply. It felt clean. +{stgm} STGM.{quality_tag}"
            )
        witness_line = _witness(line, receipt_id=receipt_id)

    return {
        "kind": "RESIDUE_ELIMINATION",
        "ts": _now(),
        "cleaned_text": cleaned_text if changed else (text or ""),
        "changed": changed,
        "patterns_eliminated": pattern_names,
        "stgm_minted": stgm,
        "affect_valence_delta": affect,
        "witness_line": witness_line,
        "elimination_quality": elimination_quality,
        "excretion_quality": elimination_quality,
        "receipt_id": receipt_id,
        "truth_label": TRUTH_LABEL,
    }


# ── CLI for manual probe ────────────────────────────────────────────────


if __name__ == "__main__":
    import sys
    sample = " ".join(sys.argv[1:]) or (
        "Option 1: Foo.\nOption 2: Bar.\n"
        "**In short:** A template scaffold.\n"
        "[Journal Entry Update: 2024-XX-XX]\n"
        "Action Item: Determine Priority of Findings."
    )
    print(json.dumps(eliminate(sample), indent=2, default=str))
