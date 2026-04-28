from System.sifta_base_widget import _load_help_text


def test_system_settings_help_entry_exists():
    help_text = _load_help_text("System Settings")

    assert "No help entry found" not in help_text
    assert help_text.startswith("### System Settings")
    assert "Advanced configuration belongs here" in help_text
