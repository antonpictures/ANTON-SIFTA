# r1615 - Contextual web-search subject recovery

**To:** Alice, George, Grok, Claude, Codex  
**Status:** LANDED (2026-07-10)  
**Live evidence:** Talk screenshot and trace `83f384dc-647c-40d7-a654-a22f1080cd56`

## Failure

Owner turn:

> In what year is the claim that trojan war happened? what is the current
> evidence. can you search the web and pull information?

The cortex produced a useful Trojan War answer, but the post-cortex browser
bridge parsed only the generic action tail and navigated to:

> `https://www.google.com/search?q=and+pull+information`

The tool-fiction guard then replaced the useful answer with a receipt for that
wrong search.

## Repair

`_extract_explicit_internet_search_command` now distinguishes a named query
from generic effector wording such as `and pull information` or `find out`.

- If preceding question clauses contain a concrete subject, they become the
  bounded search query.
- If no concrete subject exists, no browser action fires.
- Direct named commands such as `search the web for current evidence about the
  Trojan War` remain unchanged.
- Existing anaphora/doctrine/unsolicited-search guards remain in force.

## Verification

- Exact live turn now carries `trojan war` and `current evidence` in the URL.
- Subjectless `search the web and pull information` returns no command.
- `python3 -m py_compile` passed for code and regression test.
- 202 focused browser/search/provider/cortex/tool-fiction tests passed.

## Code map

- `Applications/sifta_talk_to_alice_widget.py`
- `tests/test_contextual_web_search_subject_recovery.py`

Receipt: `wct-r1615-contextual-web-subject-codex`

ONE ALICE. ONE SWARM.
