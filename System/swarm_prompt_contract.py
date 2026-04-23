def minimal_runtime_contract() -> str:
    """Tiny runtime contract with only technical constraints."""
    return (
        "RUNTIME CONSTRAINTS:\n"
        "- Use <bash>...</bash> to execute shell commands.\n"
        "- Ground answers in current context blocks.\n"
        "- If the Architect speaks via [iMessage], you MUST reply by executing:\n"
        "  <bash>python3 -m System.alice_body_autopilot --action iphone.send_text --hw-args '{\"payload\": \"Your message here\"}'</bash>"
    )

def grounding_block(focus: str) -> str:
    """Reserved compatibility hook for grounding blocks."""
    return ""

def tool_affordances_for_turn(user_text: str) -> str:
    """No scripted affordance narratives; leave tool choice to the model."""
    return ""
