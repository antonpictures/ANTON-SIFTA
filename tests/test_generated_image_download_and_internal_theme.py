from __future__ import annotations

import ast
from pathlib import Path

from System import chorus_node_server


ROOT = Path(__file__).resolve().parents[1]


def test_web_generated_image_has_download_affordance_and_attachment_header():
    source = (ROOT / "System/chorus_node_server.py").read_text()
    assert "download.href=item.url+'&download=1'" in source
    assert "download.download=item.name||'Alice-generated-image.png'" in source
    assert 'Content-Disposition", \'attachment; filename="Alice-generated-image.png"\'' in source
    assert "className='generated-image-tools'" in source


def test_internal_talk_uses_web_family_fonts_on_dark_surface():
    source = (ROOT / "Applications/sifta_talk_to_alice_widget.py").read_text()
    assert "font-family: 'Avenir Next'" in source
    assert 'body_fmt.setFontFamilies(["Avenir Next"' in source
    assert "background: #000000" in source


def test_chorus_handler_still_exposes_image_route():
    tree = ast.parse((ROOT / "System/chorus_node_server.py").read_text())
    methods = {node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)}
    assert "_handle_generated_image" in methods
