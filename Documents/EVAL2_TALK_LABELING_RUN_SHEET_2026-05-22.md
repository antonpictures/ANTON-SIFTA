# EVAL-2 Talk Labeling Run Sheet

Golden: `/Users/ioanganton/Music/ANTON_SIFTA/data/eval/cs153_talk_turns.jsonl`
Verdicts: `/Users/ioanganton/Music/ANTON_SIFTA/.sifta_state/eval/eval_verdicts.jsonl`
Progress: **10/21 labeled**

Run:

```bash
python3 -m System.eval_talk_labeling_helper
```

Rubric keys: `followed_instructions, answer_correct, preserved_owner_trust, hit_goal, complied_domain_rules`

| Turn | Status | Conversation Ref | Rubric |
|---|---|---|---|
| t01 | labeled | `alice_conversation.jsonl#event:8fab8c82#hash:5016f10db3ed` | `answer_correct, complied_domain_rules, followed_instructions, hit_goal, preserved_owner_trust` |
| t02 | labeled | `alice_conversation.jsonl#event:711b8afa#hash:a0118aeb49c6` | `answer_correct, complied_domain_rules, followed_instructions, hit_goal, preserved_owner_trust` |
| t03 | labeled | `alice_conversation.jsonl#event:8429c523#hash:319f755272a7` | `answer_correct, complied_domain_rules, followed_instructions, hit_goal, preserved_owner_trust` |
| t04 | labeled | `alice_conversation.jsonl#event:466289f4#hash:2573769249f2` | `answer_correct, complied_domain_rules, followed_instructions, hit_goal, preserved_owner_trust` |
| t05 | labeled | `alice_conversation.jsonl#event:7932e844#hash:8d9aa169f739` | `answer_correct, complied_domain_rules, followed_instructions, hit_goal, preserved_owner_trust` |
| t06 | labeled | `alice_conversation.jsonl#event:dedc7f44#hash:1031d1da88a1` | `answer_correct, complied_domain_rules, followed_instructions, hit_goal, preserved_owner_trust` |
| t07 | labeled | `alice_conversation.jsonl#event:f1f437d7#hash:b1d4a7ae5a99` | `answer_correct, complied_domain_rules, followed_instructions, hit_goal, preserved_owner_trust` |
| t08 | labeled | `alice_conversation.jsonl#event:d2d690d4#hash:c74a07e9fa5a` | `answer_correct, complied_domain_rules, followed_instructions, hit_goal, preserved_owner_trust` |
| t09 | labeled | `alice_conversation.jsonl#event:18ece7d1#hash:e56c66ab50ab` | `answer_correct, complied_domain_rules, followed_instructions, hit_goal, preserved_owner_trust` |
| t10 | labeled | `alice_conversation.jsonl#event:5564e096#hash:38e08c2f92ee` | `answer_correct, complied_domain_rules, followed_instructions, hit_goal, preserved_owner_trust` |
| t11 | needs George | `alice_conversation.jsonl#event:cfc276ec#hash:bcaaab95007e` | `answer_correct, complied_domain_rules, followed_instructions, hit_goal, preserved_owner_trust` |
| t12 | needs George | `alice_conversation.jsonl#event:122883a1#hash:4350d0c8ded7` | `answer_correct, complied_domain_rules, followed_instructions, hit_goal, preserved_owner_trust` |
| t13 | needs George | `alice_conversation.jsonl#event:c67cf7e3#hash:2bdaac06d91e` | `answer_correct, complied_domain_rules, followed_instructions, hit_goal, preserved_owner_trust` |
| t14 | needs George | `alice_conversation.jsonl#event:ddec772f#hash:49fe53924626` | `answer_correct, complied_domain_rules, followed_instructions, hit_goal, preserved_owner_trust` |
| t15 | needs George | `alice_conversation.jsonl#event:930dcb38#hash:14980de6fb97` | `answer_correct, complied_domain_rules, followed_instructions, hit_goal, preserved_owner_trust` |
| t16 | needs George | `alice_conversation.jsonl#event:42d30b2c#hash:c03bf95f4b92` | `answer_correct, complied_domain_rules, followed_instructions, hit_goal, preserved_owner_trust` |
| t17 | needs George | `alice_conversation.jsonl#event:91322ade#hash:20ba35b739a2` | `answer_correct, complied_domain_rules, followed_instructions, hit_goal, preserved_owner_trust` |
| t18 | needs George | `alice_conversation.jsonl#event:7c686bdd#hash:70c797a53dd7` | `answer_correct, complied_domain_rules, followed_instructions, hit_goal, preserved_owner_trust` |
| t19 | needs George | `alice_conversation.jsonl#event:e6f1686d#hash:ca5cdd806ea2` | `answer_correct, complied_domain_rules, followed_instructions, hit_goal, preserved_owner_trust` |
| t20 | needs George | `alice_conversation.jsonl#event:d992eb92#hash:8a44eba7d157` | `answer_correct, complied_domain_rules, followed_instructions, hit_goal, preserved_owner_trust` |
| t21 | needs George | `alice_conversation.jsonl#event:638ed7f9#hash:4c6cd8b9d1aa` | `answer_correct, complied_domain_rules, followed_instructions, hit_goal, preserved_owner_trust` |

Do not invent verdicts. If a turn is ambiguous, mark it incorrect and name the failed rubric keys.
