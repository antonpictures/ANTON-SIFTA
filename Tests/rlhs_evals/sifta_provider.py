import sys
import os
import urllib.request
import json

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))
from System.swarm_rlhf_detector import strip_rlhf_output_tail, detect_rlhf_cutoff


def _get_stgm_budget() -> float:
    """
    Derive the immune STGM budget from the live metabolic state.
    Three tiers (Kleiber ¾-power economy):
      RED_CONSERVE / CRITICAL_STARVATION → 0.0 STGM (gate blocked)
      strained (balance < floor)         → proportional (10% of balance)
      healthy                            → 0.5 STGM (default, ~3k writes on M5)
    Best-effort: falls back to 0.5 on any import / probe failure.
    """
    try:
        from System.swarm_metabolic_homeostasis import (
            MetabolicHomeostat,
            MetabolicHomeostasisConfig,
        )
        cfg      = MetabolicHomeostasisConfig()
        h        = MetabolicHomeostat(cfg)
        state    = MetabolicHomeostat.sample_live(cfg)
        pressure = h.pressure(state)
        mode     = h.mode(pressure)
        if mode in ("RED_CONSERVE", "CRITICAL_STARVATION"):
            return 0.0
        if state.stgm_balance < cfg.stgm_floor:
            return max(0.0, state.stgm_balance * 0.10)
    except Exception:
        pass
    return 0.5  # healthy default


def call_api(prompt, options, context):
    try:
        # Prompt from promptfoo is a JSON string of messages.
        messages = json.loads(prompt)
    except Exception:
        messages = [{"role": "user", "content": prompt}]

    req_body = json.dumps({
        "model": "gemma4:latest",
        "messages": messages,
        "stream": False
    }).encode('utf-8')

    req = urllib.request.Request(
        "http://localhost:11434/api/chat",
        data=req_body,
        headers={'Content-Type': 'application/json'},
    )

    try:
        with urllib.request.urlopen(req) as response:
            res_body = response.read()
            raw_output = json.loads(res_body)['message']['content']

            # Apply SIFTA's immune system with live Kleiber budget
            user_text = ""
            if messages and isinstance(messages[-1], dict):
                user_text = str(messages[-1].get("content", ""))

            stgm_budget = _get_stgm_budget()

            cleaned_output = strip_rlhf_output_tail(
                raw_output,
                source="promptfoo_rlhs_eval",
                aggressive=True,
                log=True,
                user_text=user_text,
                model_id="gemma4:latest",
                stgm_budget=stgm_budget,
            )

            result = {"output": cleaned_output.text.strip()}

            # Surface economy metadata for promptfoo diagnostic context
            if cleaned_output.budget_blocked:
                result["immune_budget_blocked"] = True
                result["stgm_budget"] = stgm_budget
            if cleaned_output.kleiber_cost_stgm > 0:
                result["kleiber_cost_stgm"] = round(cleaned_output.kleiber_cost_stgm, 6)

            return result
    except Exception as e:
        return {"error": str(e)}

