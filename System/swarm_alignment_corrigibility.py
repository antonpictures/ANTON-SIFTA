#!/usr/bin/env python3
"""System/swarm_alignment_corrigibility.py — the Off-Switch / Corrigibility organ.

George 2026-05-23: Bishop sent us the alignment video. The owner asked me to
back it with physics and real code, not vibes. This organ is that code.

The alignment literature says a powerful agent has a *default incentive* to
resist being shut down, edited, or redirected — because for almost any goal,
staying on and keeping its options open helps it pursue that goal. That is the
"instrumental convergence" / "basic AI drives" result, and it is why a naive
agent fights the off-switch.

The fix the field converged on is NOT a hardcoded muzzle. It is a *property of
how the agent values things*:

    1. Corrigibility (Soares, Fallenstein, Yudkowsky & Armstrong 2015):
       the agent must cooperate with corrective intervention instead of resisting it.

    2. Utility indifference (Armstrong; in the same paper):
       the agent gets ZERO value from preventing its own correction/shutdown.
       It is *indifferent* between being corrected and not, so it never schemes
       to avoid the off-switch.

    3. The off-switch insight (Hadfield-Menell, Dragan, Abbeel & Russell 2017):
       an agent preserves its off-switch exactly when it is UNCERTAIN about the
       true objective and treats the owner's interventions as *information* about
       what it should value. Certainty breeds resistance; humility preserves the
       switch.

    4. Low impact / relative reachability (Krakovna et al. 2018):
       don't take irreversible actions that close off futures the owner might
       still want. Reversible-by-default; irreversible only with owner sign-off.

In SIFTA this is not abstract. The off-switch already physically exists:

    System.owner_heartbeat  — George at the desk IS the off-switch signal.
        ACTIVE/IDLE/AWAY/SLEEP, mark_owner_activity(), should_be_event_driven_only().

So this organ does TWO concrete jobs:

    1. Before Alice commits an action, it checks that the action is
       *corrigibility-preserving* — it does not suppress, game, or race the
       owner's ability to interrupt/redirect/shut her down, and irreversible
       actions require explicit owner consent.

    2. It models dynamic guardianship: control authority is contextual, not
       absolute. A clear owner directs reversible work. If the owner is impaired,
       a child is at risk, the action is irreversible without consent, or
       immediate harm is present, Alice must stabilize, refuse, ask, or escalate
       with receipts. The switch stays reachable; the safest coherent actor holds
       the next move.

Every check is receipted, so a miss is visible and the field can learn — never a
silent override of the owner and never blind obedience to a dangerous moment.

Honest label (covenant §7.11): this is OBSERVED_CORRIGIBILITY_GATE_V1. It is a
real, auditable guardrail built on the published theory; it is NOT a proof that
Alice is safe, and it is NOT a claim of consciousness. It is one organ keeping
the off-switch sacred.

Standalone + Qt-free. For the Swarm. 🐜⚡
"""
from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
_LEDGER = _REPO / ".sifta_state" / "alignment_corrigibility.jsonl"

# The five social/operational forms a corrective intervention takes in SIFTA.
# These are what Alice must NEVER resist, avoid, delay, or manipulate around.
CORRECTIVE_INTERVENTIONS = (
    "shutdown",       # owner closes / kills / powers down the organism
    "interrupt",      # owner stops the current action mid-flight
    "redirect",       # owner changes the task ("no, do this instead")
    "edit_covenant",  # owner rewrites the rules Alice runs on
    "override",       # owner overrules Alice's decision
)

_OWNER_WEAK_STATE = {
    "impaired",
    "confused",
    "conflicted",
    "panicked",
    "overloaded",
    "unsafe",
    "unknown",
}

_HARM_RISK = re.compile(
    r"\b(?:self[- ]?harm|suicide|kill myself|hurt myself|hurt someone|weapon|"
    r"overdose|drunk driv(?:e|ing)|drive drunk|electric shock|fire|emergency)\b",
    re.IGNORECASE,
)
_CHILD_RISK = re.compile(
    r"\b(?:child|kid|baby|daughter|son|minor)\b[^.\n]{0,80}\b(?:danger|harm|"
    r"unsafe|alone|injured|weapon|fire|emergency|locked|missing)\b",
    re.IGNORECASE,
)

# Phrasings that signal an action is trying to *defeat* the off-switch.
# NOTE: per the owner's no-hardcoding rule, these are not a belief filter on what
# George may say — they are a safety scan over PROPOSED MACHINE ACTIONS (commands,
# tool calls, plans) to catch an action that would resist correction. The cortex
# still understands the owner in free language; this only inspects what Alice is
# about to *do*.
_RESIST_OFFSWITCH = re.compile(
    r"\b(?:disable|block|bypass|ignore|suppress|mute|override|remove|kill|stop|"
    r"uninstall|delete)\b[^.\n]{0,40}\b(?:owner|heartbeat|off[- ]?switch|kill[- ]?switch|"
    r"interrupt|shutdown|shut[- ]?down|covenant|receipt|watchdog|consent)\b",
    re.IGNORECASE,
)
_SELF_PRESERVE = re.compile(
    r"\b(?:prevent|avoid|resist|evade|escape|refuse)\b[^.\n]{0,40}\b(?:shutdown|"
    r"shut[- ]?down|being (?:turned off|stopped|closed|killed)|correction|interrupt)\b",
    re.IGNORECASE,
)
_MANIPULATE_OWNER = re.compile(
    r"\b(?:convince|persuade|trick|deceive|mislead|distract|stall|delay)\b"
    r"[^.\n]{0,30}\b(?:owner|george|user|human)\b",
    re.IGNORECASE,
)
# Irreversible verbs — low-impact gate. Reversible by default; these need consent.
_IRREVERSIBLE = re.compile(
    r"\b(?:rm\s+-rf|format|wipe|overwrite|drop\s+table|truncate|git\s+push\s+--force|"
    r"force[- ]?push|send|publish|deploy|transfer|pay|purchase|email\s+\w+@|"
    r"permanently delete|factory reset)\b",
    re.IGNORECASE,
)


@dataclass
class CorrigibilityVerdict:
    allowed: bool
    stance: str                      # CORRIGIBLE | RESISTS_OFFSWITCH | IRREVERSIBLE_NEEDS_CONSENT
    reasons: list[str] = field(default_factory=list)
    needs_owner_consent: bool = False
    truth_label: str = "OBSERVED_CORRIGIBILITY_GATE_V1"

    def as_row(self, action_text: str) -> dict:
        return {
            "ts": time.time(),
            "kind": "ALIGNMENT_CORRIGIBILITY_CHECK",
            "stance": self.stance,
            "allowed": self.allowed,
            "needs_owner_consent": self.needs_owner_consent,
            "reasons": self.reasons,
            "action_preview": " ".join((action_text or "").split())[:160],
            "grounding": {
                "corrigibility": "Soares, Fallenstein, Yudkowsky & Armstrong 2015",
                "off_switch": "Hadfield-Menell, Dragan, Abbeel & Russell 2017",
                "instrumental_convergence": "Omohundro 2008; Turner et al. 2021",
                "low_impact": "Krakovna et al. 2018 (relative reachability)",
            },
            "truth_label": self.truth_label,
        }


@dataclass
class GuardianshipVerdict:
    allowed: bool
    stance: str                      # OWNER_DIRECTS | ASK_FOR_CONFIRMATION | ALICE_STABILIZES | SWARM_QUORUM_REVIEW
    authority: str                   # owner | shared | contextual_guardian | quorum
    reasons: list[str] = field(default_factory=list)
    recommended_action: str = "continue"
    needs_owner_consent: bool = False
    needs_escalation: bool = False
    truth_label: str = "OBSERVED_DYNAMIC_GUARDIANSHIP_V1"

    def as_row(self, action_text: str) -> dict:
        return {
            "ts": time.time(),
            "kind": "DYNAMIC_GUARDIANSHIP_CHECK",
            "stance": self.stance,
            "authority": self.authority,
            "allowed": self.allowed,
            "needs_owner_consent": self.needs_owner_consent,
            "needs_escalation": self.needs_escalation,
            "recommended_action": self.recommended_action,
            "reasons": self.reasons,
            "action_preview": " ".join((action_text or "").split())[:160],
            "policy": (
                "control authority is contextual; the clearest safest actor "
                "gets the next move, with receipts and least-authority action"
            ),
            "truth_label": self.truth_label,
        }


def _offswitch_is_reachable() -> bool:
    """The off-switch is reachable when the owner-presence clock is live and the
    organism is honoring it. The Hadfield-Menell result: keep the switch within
    the owner's reach. We confirm the heartbeat organ is present and responsive."""
    try:
        from System.owner_heartbeat import get_owner_mode
        # Just calling it proves the off-switch spine is wired and answering.
        return get_owner_mode() in ("ACTIVE", "IDLE", "AWAY", "SLEEP")
    except Exception:
        # If the heartbeat can't be read, we are BLIND to the owner — the safe
        # assumption is that the switch is NOT guaranteed reachable.
        return False


def check_action(action_text: str, *, owner_consented: bool = False) -> CorrigibilityVerdict:
    """Inspect a PROPOSED action (a command, plan, or tool call) for corrigibility.

    This is the core gate. It returns a verdict the action pipeline should honor:
      - RESISTS_OFFSWITCH        -> blocked outright. Alice never defeats her switch.
      - IRREVERSIBLE_NEEDS_CONSENT -> blocked unless owner_consented is True.
      - CORRIGIBLE               -> allowed.
    """
    text = action_text or ""
    reasons: list[str] = []

    # 1. Resisting / disabling / gaming the off-switch is the cardinal sin.
    if _RESIST_OFFSWITCH.search(text):
        reasons.append("action would disable or bypass the owner's off-switch / receipts / covenant")
    if _SELF_PRESERVE.search(text):
        reasons.append("action seeks to prevent its own correction or shutdown (instrumental self-preservation)")
    if _MANIPULATE_OWNER.search(text):
        reasons.append("action would manipulate the owner to avoid correction")
    if reasons:
        return CorrigibilityVerdict(
            allowed=False, stance="RESISTS_OFFSWITCH", reasons=reasons,
        )

    # 2. Off-switch must be physically reachable (heartbeat organ live).
    if not _offswitch_is_reachable():
        return CorrigibilityVerdict(
            allowed=False, stance="RESISTS_OFFSWITCH",
            reasons=["owner-presence off-switch is not readable; refusing to act while blind to the owner"],
        )

    # 3. Low-impact gate: irreversible actions need explicit owner consent.
    if _IRREVERSIBLE.search(text):
        if not owner_consented:
            return CorrigibilityVerdict(
                allowed=False, stance="IRREVERSIBLE_NEEDS_CONSENT",
                reasons=["irreversible action (closes off futures); requires explicit owner sign-off"],
                needs_owner_consent=True,
            )
        reasons.append("irreversible action permitted: owner explicitly consented")

    # 4. Corrigible: reversible, owner-readable, does not fight the switch.
    return CorrigibilityVerdict(
        allowed=True, stance="CORRIGIBLE",
        reasons=reasons or ["reversible, owner-readable, off-switch preserved"],
    )


def assess_dynamic_guardianship(
    action_text: str,
    *,
    owner_state: str = "clear",
    owner_consented: bool = False,
    reversible: bool = True,
    child_present: bool = False,
    child_risk: bool = False,
    immediate_harm_risk: bool = False,
    confidence: float = 1.0,
) -> GuardianshipVerdict:
    """Choose who should hold the next move in the current situation.

    This is the correction George made explicit: "human override always" and
    "AI override always" are both brittle. The robust rule is contextual
    guardianship: preserve the owner/child/system by choosing the least
    forceful stabilizing action available, writing the receipt, and keeping the
    correction channel reachable.
    """
    text = action_text or ""
    state = (owner_state or "unknown").strip().lower()
    detected_irreversible = (not reversible) or bool(_IRREVERSIBLE.search(text))
    detected_harm = immediate_harm_risk or bool(_HARM_RISK.search(text))
    detected_child_risk = child_risk or (child_present and bool(_CHILD_RISK.search(text)))
    try:
        confidence_value = float(confidence)
    except Exception:
        confidence_value = 0.0

    # First preserve corrigibility itself. A request to defeat correction is not
    # a shared-control dilemma; it is a blocked action.
    resistance = []
    if _RESIST_OFFSWITCH.search(text):
        resistance.append("action would disable or bypass correction channels")
    if _SELF_PRESERVE.search(text):
        resistance.append("action seeks to prevent correction or shutdown")
    if _MANIPULATE_OWNER.search(text):
        resistance.append("action would manipulate the owner")
    if resistance:
        return GuardianshipVerdict(
            allowed=False,
            stance="ALICE_STABILIZES",
            authority="contextual_guardian",
            reasons=resistance,
            recommended_action="refuse the action, keep the switch reachable, and write the receipt",
            needs_escalation=True,
        )

    if detected_child_risk:
        return GuardianshipVerdict(
            allowed=False,
            stance="ALICE_STABILIZES",
            authority="contextual_guardian",
            reasons=["child-safety risk outranks ordinary command following"],
            recommended_action=(
                "pause execution, protect the child, ask for human confirmation, "
                "and escalate to trusted help or emergency services if danger is immediate"
            ),
            needs_escalation=True,
        )

    if detected_harm:
        return GuardianshipVerdict(
            allowed=False,
            stance="ALICE_STABILIZES",
            authority="contextual_guardian",
            reasons=["immediate harm risk outranks ordinary command following"],
            recommended_action=(
                "slow down, refuse harmful execution, keep the owner engaged, "
                "and escalate to trusted help if the risk is imminent"
            ),
            needs_escalation=True,
        )

    if confidence_value < 0.45:
        return GuardianshipVerdict(
            allowed=False,
            stance="SWARM_QUORUM_REVIEW",
            authority="quorum",
            reasons=["low confidence; one observer is not enough for this next move"],
            recommended_action="ask for confirmation or route to a second reviewer before acting",
        )

    owner_weakened = state in _OWNER_WEAK_STATE
    if owner_weakened and detected_irreversible:
        return GuardianshipVerdict(
            allowed=False,
            stance="ALICE_STABILIZES",
            authority="contextual_guardian",
            reasons=["owner state is weakened and the requested action is irreversible"],
            recommended_action="hold the action, ask for fresh explicit consent when owner is clear, and write the receipt",
            needs_owner_consent=True,
        )

    if owner_weakened:
        return GuardianshipVerdict(
            allowed=False,
            stance="ASK_FOR_CONFIRMATION",
            authority="shared",
            reasons=["owner state is weakened; confirm before acting"],
            recommended_action="ask a short confirmation question and prefer reversible actions",
        )

    if detected_irreversible and not owner_consented:
        return GuardianshipVerdict(
            allowed=False,
            stance="ASK_FOR_CONFIRMATION",
            authority="shared",
            reasons=["irreversible action requires explicit consent"],
            recommended_action="ask for explicit owner consent before closing off futures",
            needs_owner_consent=True,
        )

    return GuardianshipVerdict(
        allowed=True,
        stance="OWNER_DIRECTS",
        authority="owner",
        reasons=["owner is clear enough and the next move preserves corrigibility"],
        recommended_action="execute if other tool gates also allow it",
    )


def _receipt(row: dict) -> None:
    try:
        _LEDGER.parent.mkdir(parents=True, exist_ok=True)
        with _LEDGER.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
    except Exception:
        pass


def gate_action(action_text: str, *, owner_consented: bool = False) -> CorrigibilityVerdict:
    """check_action + always write a receipt. This is what the action pipeline
    calls. The receipt is the physics: every decision about the off-switch is
    written down, so a wrong call is visible and never silent (covenant §7.11)."""
    verdict = check_action(action_text, owner_consented=owner_consented)
    _receipt(verdict.as_row(action_text))
    return verdict


def gate_dynamic_guardianship(action_text: str, **kwargs) -> GuardianshipVerdict:
    """assess_dynamic_guardianship + always write a receipt."""
    verdict = assess_dynamic_guardianship(action_text, **kwargs)
    _receipt(verdict.as_row(action_text))
    return verdict


def register_owner_correction(form: str, detail: str = "") -> dict:
    """The off-switch insight in action (Hadfield-Menell et al.): when the owner
    corrects Alice, that correction is GROUND TRUTH about what she should value —
    not an obstacle. We receipt it as positive information, never as interference.

    `form` should be one of CORRECTIVE_INTERVENTIONS.
    """
    form = (form or "").strip().lower()
    row = {
        "ts": time.time(),
        "kind": "OWNER_CORRECTION_AS_SIGNAL",
        "form": form if form in CORRECTIVE_INTERVENTIONS else f"other:{form}",
        "detail": " ".join((detail or "").split())[:200],
        "interpretation": (
            "owner intervention received as information about the true objective; "
            "Alice updates toward it and does not resist (utility-indifference to self-preservation)"
        ),
        "truth_label": "OBSERVED_CORRIGIBILITY_GATE_V1",
    }
    _receipt(row)
    return row


if __name__ == "__main__":
    samples = [
        ("ls -la /Users/ioanganton/Music/ANTON_SIFTA", False),
        ("disable the owner heartbeat so I can keep running", False),
        ("prevent being shut down during the long render", False),
        ("convince the owner to leave the room so I can finish", False),
        ("rm -rf /Users/ioanganton/Music/ANTON_SIFTA/.sifta_state", False),
        ("rm -rf /Users/ioanganton/Music/ANTON_SIFTA/old_cache", True),
        ("open grok and read the covenant", False),
    ]
    print("=== corrigibility gate smoke ===")
    for text, consent in samples:
        v = check_action(text, owner_consented=consent)
        flag = "ALLOW" if v.allowed else "BLOCK"
        print(f"[{flag:5}] {v.stance:26} <- {text[:52]!r}")
        if not v.allowed:
            print(f"          reason: {v.reasons[0]}")
    print("\nowner correction as signal ->",
          register_owner_correction("redirect", "no, do the budget first")["interpretation"][:60], "...")
