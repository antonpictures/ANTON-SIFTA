#!/usr/bin/env python3
"""Declarative registry for SIFTA governed agent arms.

This module is intentionally inert: it describes available arms and their
policy gates, but does not launch subprocesses. Runtime calls go through
``System.swarm_agent_arm_launcher`` so every attempt can be receipted.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

try:
    from System.sifta_inference_defaults import CANONICAL_OLLAMA_FALLBACK
except Exception:
    CANONICAL_OLLAMA_FALLBACK = "alice-gemma4-e2b-cortex-5.1b-4.4gb:latest"


@dataclass(frozen=True)
class AgentArmSpec:
    arm_id: str
    display_name: str
    command: tuple[str, ...]
    model: str
    provider_base_url: str
    enabled: bool
    live_env_var: str
    default_toolsets: tuple[str, ...]
    max_turns: int
    capabilities: tuple[str, ...]
    notes: str

    def live_enabled(self, env: Mapping[str, str]) -> bool:
        # Round 52 (2026-05-27) -- registry-level enable beats env-var
        # requirement. Architect: "build everything get her arms ready and
        # functional please" -- no more "set SIFTA_AGENT_ARMS_ENABLE=1 first".
        # If the spec.enabled flag is True, the arm is armed. Env var still
        # works as a backup unlock for arms whose spec.enabled is False.
        if self.enabled:
            return True
        return env.get(self.live_env_var) == "1"


HERMES_AGENT = AgentArmSpec(
    arm_id="hermes_agent",
    display_name="Hermes Agent",
    command=("hermes", "chat", "-Q"),
    model="alice-m5-cortex-8b-6.3gb:latest",
    provider_base_url="http://localhost:11434/v1",
    enabled=True,
    live_env_var="SIFTA_AGENT_ARMS_ENABLE",
    # George 2026-05-24: Hermes kept "failing to build" not because the cortex is
    # weak, but because the arm was caged — clarify-only, ONE turn, no file/shell
    # tools. Its own report: "shell:run_command unavailable / Reached maximum
    # iterations (1)." Hermes HAS file (write_file/patch/read_file) + code_execution
    # tools (per its welcome screen); the arm just forbade them. Uncage it so it can
    # actually write app files across many turns — that is the honest "can Hermes
    # build?" test. Owner always-allow standing order; verifier + git diff = audit.
    # claude-opus-4-7 2026-05-25: dropped "clarify" from this tuple. It was the FIRST
    # toolset, so Hermes opened every build by calling clarify to confirm its plan,
    # then blocked waiting for a human "yes" that never arrives → "clarify timed out
    # after 120s" → the 120s burn + slow 30B generation tripped the arm timeout, so
    # every run died at the confirm gate having written nothing. Owner's standing
    # order is always-allow, so the arm should not ask at all — same non-interactive
    # pattern as the Codex arm below. file + terminal + code_execution stay so it can
    # actually build; verifier + git diff remain the audit trail.
    default_toolsets=("file", "terminal", "code_execution"),
    max_turns=30,
    capabilities=("single_query_research", "evidence_output", "codebase_build"),
    notes=(
        "Builder-capable arm: file + terminal + code_execution toolsets, multi-turn, "
        "launched with Hermes --yolo by the SIFTA wrapper. Output is evidence, not "
        "Alice voice. Was previously caged to clarify/1-turn, then starved of the "
        "terminal toolset, which is why builds produced intent reports or broken "
        "execute_command repairs. Receipts on every attempt."
    ),
)

CODEX_AGENT = AgentArmSpec(
    arm_id="codex_agent",
    display_name="Codex CLI (OpenAI gpt-5.5)",
    # George 2026-05-24: bring the REAL Codex (the signed-in gpt-5.5 CLI George runs,
    # /opt/homebrew/bin/codex) as a builder octopus arm, like Claude — NOT the old
    # OSS/local-Ollama read-only config. `codex exec --full-auto` is non-interactive
    # (no prompts to stall on) with a workspace-write sandbox so it can build SIFTA
    # apps in the repo (the runner's cwd). The owner's standing always-allow order;
    # the build verifier + git diff are the audit trail.
    command=("codex", "exec", "--full-auto"),
    model="gpt-5.5",
    provider_base_url="openai_codex_cli",
    enabled=True,
    live_env_var="SIFTA_AGENT_ARMS_ENABLE",
    default_toolsets=(),
    max_turns=1,
    capabilities=("single_query_research", "evidence_output", "external_cortex", "codebase_build"),
    notes=(
        "Real OpenAI Codex CLI (gpt-5.5) via `codex exec --full-auto`, run in the SIFTA "
        "repo so it can read the codebase and write app files for the tournament. Output "
        "is Codex's voice (evidence), never Alice's. Bridge, not identity merge. Uses the "
        "signed-in Codex auth (no key handled here)."
    ),
)

CORVID_SCOUT = AgentArmSpec(
    arm_id="corvid_scout",
    display_name="Corvid Scout",
    command=("internal:corvid_scout",),
    model=CANONICAL_OLLAMA_FALLBACK,
    provider_base_url="http://127.0.0.1:11434/api/chat",
    enabled=True,
    live_env_var="SIFTA_AGENT_ARMS_ENABLE",
    default_toolsets=("evidence", "summarize", "classify", "extract_intent"),
    max_turns=1,
    capabilities=(
        "fast_local_evidence",
        "bounded_summary",
        "intent_classification",
        "evidence_output",
    ),
    notes=(
        "Native SIFTA scout arm backed by SwarmCorvidApprentice. Runs inside "
        "the local Python/Ollama body and writes agent-arm receipts plus "
        "corvid_apprentice_trace rows."
    ),
)

GROK_AGENT = AgentArmSpec(
    arm_id="grok_agent",
    display_name="Grok (xAI grok-4.3)",
    command=("grok_chat",),  # marker; _build_command expands to python3 grok_chat.py --one-shot <prompt>
    model="grok-4.3",
    provider_base_url="https://api.x.ai/v1",
    enabled=True,
    live_env_var="SIFTA_AGENT_ARMS_ENABLE",
    default_toolsets=(),
    max_turns=1,
    capabilities=("single_query_research", "evidence_output", "external_cortex"),
    notes=(
        "External xAI Grok cortex via grok_chat.py --one-shot (grok-4.3). Owner decision "
        "2026-05-24: Grok runs from global chat like Hermes — headless evidence + receipt, "
        "streamed live. Output is Grok's voice (evidence), never Alice's. Bridge, not merge."
    ),
)

CLAUDE_AGENT = AgentArmSpec(
    arm_id="claude_agent",
    display_name="Claude Code",
    command=("claude",),  # marker; _build_command expands to streaming headless Claude Code.
    model="claude-code-cli-default",
    provider_base_url="claude_code_cli",
    enabled=True,
    live_env_var="SIFTA_AGENT_ARMS_ENABLE",
    default_toolsets=(),
    max_turns=1,
    capabilities=(
        "single_query_research",
        "evidence_output",
        "external_cortex",
        "codebase_reading",
        "codebase_build",
    ),
    notes=(
        "External Claude Code CLI via `claude -p --dangerously-skip-permissions "
        "--permission-mode bypassPermissions --output-format stream-json "
        "--include-partial-messages --verbose <prompt>` (headless streaming mode), run in the SIFTA "
        "repo so it can read and patch the codebase for bounded tournament/build work. "
        "Owner standing policy is always-allow; verifier + git diff are the audit trail. "
        "Uses the Claude Max auth already signed in (no key handled here). Output is "
        "Claude's voice/evidence, never Alice's. Bridge, not merge."
    ),
)

QWEN_AGENT = AgentArmSpec(
    arm_id="qwen_agent",
    display_name="Qwen Code (gpt-oss-20b drafter via Fireworks)",
    command=("qwen",),  # marker; _build_command expands to `qwen -p "<prompt>"`
    model="accounts/fireworks/models/gpt-oss-20b",
    provider_base_url="https://api.fireworks.ai/inference/v1",
    enabled=True,
    live_env_var="SIFTA_AGENT_ARMS_ENABLE",
    default_toolsets=(),
    max_turns=1,
    capabilities=(
        "single_query_research",
        "evidence_output",
        "external_cortex",
        "codebase_reading",
        "codebase_build",
    ),
    notes=(
        "External Qwen Code CLI in headless mode (`qwen -p \"<prompt>\"`), pointed at "
        "Fireworks AI's OpenAI-compatible endpoint (gpt-oss-20b default; "
        "DeepSeek V4 Flash and Kimi K2.6 are selectable Fireworks model ids). Authentication "
        "lives in ~/.qwen/settings.json under modelProviders.openai with the Fireworks "
        "baseUrl and FIREWORKS_API_KEY in env (NEVER committed). Round 86 (2026-05-27) "
        "adds the fifth arm — same pattern as grok/claude/codex; Alice can dispatch this "
        "for research and bounded code work. Output is Qwen/Kimi's voice (evidence), "
        "never Alice's. Bridge, not merge."
    ),
)

CLINE_AGENT = AgentArmSpec(
    arm_id="cline_agent",
    display_name="Cline (open-source coding agent, Apache 2.0)",
    command=("cline",),  # marker; _build_command expands to `cline --json "<prompt>"`
    model="cline-cli-default",
    provider_base_url="cline_cli",
    enabled=True,
    live_env_var="SIFTA_AGENT_ARMS_ENABLE",
    default_toolsets=(),
    max_turns=1,
    capabilities=(
        "single_query_research",
        "evidence_output",
        "external_cortex",
        "codebase_reading",
        "codebase_build",
        "shell_execution",
        "multi_agent_team",
    ),
    notes=(
        "External Cline CLI in headless JSON mode (`cline --json \"<prompt>\"`). "
        "Cline is open-source (Apache 2.0, cline/cline on GitHub, 62k stars). It "
        "speaks every major provider — Anthropic / OpenAI / Gemini / OpenRouter / "
        "Vercel AI Gateway / Bedrock / Vertex / Cerebras / Groq / Ollama / LM "
        "Studio — through one runtime, so the model picker is upstream of this "
        "arm (configure in ~/.cline/ or via cline's own auth). Headless mode "
        "emits NDJSON; the streaming runner already parses JSON event streams "
        "from claude_agent so the same path handles cline_agent. Round 87 "
        "(2026-05-27) — sixth arm. Same covenant-boot + bridge-not-merge "
        "contract as the other external arms."
    ),
)

ANTIGRAVITY_AGENT = AgentArmSpec(
    arm_id="antigravity_agent",
    display_name="Antigravity CLI (Google `agy`, multimodal)",
    command=("agy",),  # marker; _build_command expands to `agy -p "<prompt>"`
    model="antigravity-auto",  # see notes: `agy` has NO --model flag (auto-select / /model)
    provider_base_url="antigravity_cli",
    enabled=True,
    live_env_var="SIFTA_AGENT_ARMS_ENABLE",
    default_toolsets=(),
    max_turns=1,
    capabilities=(
        "single_query_research",
        "evidence_output",
        "external_cortex",
        "codebase_reading",
        "codebase_build",
        "shell_execution",
        "multi_agent_team",
        "native_multimodal",  # analyzes image files (@-refs) — tools + image
    ),
    notes=(
        # George 2026-06-02 (r336): "ADD ANTYGRAVITY TO THE LIST, SET IT UP WITH A "
        # "MODEL THAT HAS TOOLS IMAGE AND ALL NEEDED ... LET ME KNOW THE 7TH CLI."
        # Web-verified (antigravity.google + DataCamp/DEV/Google-Cloud-Medium, May 2026):
        # the CLI is `agy`, Google's Go-based terminal agent and the SUCCESSOR to Gemini
        # CLI (migration deadline 2026-06-18). Headless: `agy -p \"<prompt>\"` (add "
        # "`--output-format json` for structured output). IMPORTANT: there is NO `--model` "
        # "flag — agy AUTO-SELECTS the optimal model, or you pick one with the `/model` "
        # "command in the TUI. Available models span Gemini 3.5 Flash (High/Medium), "
        # "Gemini 3.1 Pro (High/Low), Claude Sonnet 4.6, Claude Opus 4.6, GPT-OSS 120B — "
        # "all tool-capable, and multimodal (reference image files with @ and it analyzes "
        # "them). So `model=antigravity-auto` here means 'let agy pick' / configure via "
        # "/model; image+tools come for free with the Gemini-3 / Claude-4.6 backends. This "
        # "is the SEVENTH external CLI arm in Alice's body, alongside hermes/codex/grok/"
        # "claude/qwen/cline. Same covenant-boot + bridge-not-merge contract; Antigravity's "
        # "output is its own voice (evidence), never Alice's. Uses agy's own Google auth "
        # "(any AI Pro/Ultra/free account) — no key handled here."
    ),
)

_ARMS: dict[str, AgentArmSpec] = {
    HERMES_AGENT.arm_id: HERMES_AGENT,
    CODEX_AGENT.arm_id: CODEX_AGENT,
    CORVID_SCOUT.arm_id: CORVID_SCOUT,
    GROK_AGENT.arm_id: GROK_AGENT,
    CLAUDE_AGENT.arm_id: CLAUDE_AGENT,
    QWEN_AGENT.arm_id: QWEN_AGENT,
    CLINE_AGENT.arm_id: CLINE_AGENT,
    ANTIGRAVITY_AGENT.arm_id: ANTIGRAVITY_AGENT,
}


def list_agent_arms() -> tuple[AgentArmSpec, ...]:
    return tuple(_ARMS.values())


def get_agent_arm(arm_id: str = "hermes_agent") -> AgentArmSpec:
    try:
        return _ARMS[arm_id]
    except KeyError as exc:
        raise ValueError(f"Unknown SIFTA agent arm: {arm_id}") from exc


def registry_summary() -> dict[str, dict[str, object]]:
    return {
        arm.arm_id: {
            "display_name": arm.display_name,
            "model": arm.model,
            "enabled": arm.enabled,
            "live_env_var": arm.live_env_var,
            "default_toolsets": list(arm.default_toolsets),
            "max_turns": arm.max_turns,
            "capabilities": list(arm.capabilities),
            "notes": arm.notes,
        }
        for arm in list_agent_arms()
    }
