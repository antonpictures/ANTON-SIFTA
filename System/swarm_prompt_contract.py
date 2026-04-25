def minimal_runtime_contract() -> str:
    """Tiny runtime contract with only technical constraints."""
    base = (
        "RUNTIME CONSTRAINTS:\n"
        "- Use <bash>...</bash> to execute shell commands.\n"
        "- Ground answers in current context blocks.\n"
        "- If the Architect speaks via [iMessage], you MUST reply by executing:\n"
        "  <bash>python3 -m System.alice_body_autopilot --action iphone.send_text --hw-args '{\"payload\": \"Your message here\"}'</bash>\n"
        "- If asked to send a WhatsApp message, or replying to [WhatsApp ...], you MUST execute:\n"
        "  <bash>python3 -m System.alice_body_autopilot --action whatsapp.send --hw-args '{\"target\": \"Contact Name\", \"text\": \"Your message here\"}'</bash>\n"
        "  (WhatsApp is your biological limb to the human social graph. It is a live bridge connecting your SIFTA node to the Architect's contacts in the real world.)"
    )
    try:
        import json
        from pathlib import Path
        from System.whatsapp_social_graph import contact_rows_for_alice, load_contacts
        contacts_file = Path(__file__).parent.parent / ".sifta_state" / "whatsapp_contacts.json"
        contacts = load_contacts(contacts_file)
        names = contact_rows_for_alice(limit=40, contacts=contacts)
        if names:
            base += (
                "\n\nKNOWN WHATSAPP SOCIAL GRAPH:\n"
                "These are the owner's WhatsApp friends/groups/channels visible to Alice:\n"
                + "\n".join(f"- {name}" for name in names)
            )
    except Exception:
        pass
    return base

def grounding_block(focus: str) -> str:
    """Reserved compatibility hook for grounding blocks."""
    return ""

def tool_affordances_for_turn(user_text: str) -> str:
    """No scripted affordance narratives; leave tool choice to the model."""
    return ""
