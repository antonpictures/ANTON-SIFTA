import json
from pathlib import Path

from System.whatsapp_social_graph import (
    contact_rows_for_alice,
    enrich_contact_record,
    migrate_existing_contacts,
    resolve_target,
    save_contacts,
    summary_for_alice,
)


def test_enrich_contact_marks_owner_social_graph():
    row = enrich_contact_record(
        {},
        jid="15551234567@s.whatsapp.net",
        name="Carlton",
        now=1000.0,
    )

    assert row["owner_social_graph"] is True
    assert row["relationship_to_owner"] == "whatsapp_contact"
    assert "owner's WhatsApp account" in row["relationship_note"]
    assert row["display_name"] == "Carlton"


def test_group_and_direct_resolution_disambiguates_by_suffix():
    contacts = {
        "direct": enrich_contact_record({}, jid="15551234567@s.whatsapp.net", name="Jeff", now=1),
        "group": enrich_contact_record({}, jid="120363408204674197@g.us", name="Jeff", now=2),
    }

    assert resolve_target("Jeff", contacts) == ""
    assert resolve_target("Jeff group", contacts) == "120363408204674197@g.us"
    assert resolve_target("Jeff direct", contacts) == "15551234567@s.whatsapp.net"


def test_summary_names_owner_social_graph(monkeypatch, tmp_path):
    contacts_path = tmp_path / "whatsapp_contacts.json"
    save_contacts(
        {
            "group": enrich_contact_record(
                {},
                jid="120363408204674197@g.us",
                name="SIFTA",
                now=2,
            )
        },
        contacts_path,
    )

    monkeypatch.setattr("System.whatsapp_social_graph.CONTACTS_FILE", contacts_path)
    summary = summary_for_alice()

    assert "WHATSAPP SOCIAL GRAPH:" in summary
    assert "machine owner's real social graph" in summary
    assert "SIFTA (group, owner social graph)" in summary


def test_migrate_existing_contacts_adds_social_fields(tmp_path):
    contacts_path = tmp_path / "whatsapp_contacts.json"
    contacts_path.write_text(
        json.dumps(
            {
                "abc": {
                    "jid": "120363408204674197@g.us",
                    "display_name": "SIFTA",
                    "chat_type": "group",
                }
            }
        ),
        encoding="utf-8",
    )

    assert migrate_existing_contacts(contacts_path) == 1
    migrated = json.loads(contacts_path.read_text(encoding="utf-8"))
    row = migrated["abc"]

    assert row["owner_social_graph"] is True
    assert row["relationship_to_owner"] == "whatsapp_group"
    assert contact_rows_for_alice(contacts=migrated) == ["SIFTA (group, owner social graph)"]
