import ast
from pathlib import Path

# Mermaid release baseline: keep the widget from growing further until logic is
# extracted into System/ services.
WIDGET_MAX_LINES = 3140

# At the time of the C55M Independent Audit, there were 32 top-level classes/functions.
# Any new capabilities must be extracted into modular `System/` microservices.
WIDGET_MAX_TOPLEVEL_NODES = 32

def test_widget_line_count():
    widget_path = Path(__file__).parent.parent / "Applications" / "sifta_talk_to_alice_widget.py"
    assert widget_path.exists(), "Widget file not found."
    
    with open(widget_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
        
    line_count = len(lines)
    assert line_count <= WIDGET_MAX_LINES, (
        f"HARD BOUNDARY EXCEEDED: Widget is {line_count} lines. "
        f"C47H ratchet locked at {WIDGET_MAX_LINES}. Do not add cruft. "
        "Move logic to System/."
    )

def test_widget_toplevel_node_count():
    widget_path = Path(__file__).parent.parent / "Applications" / "sifta_talk_to_alice_widget.py"
    assert widget_path.exists(), "Widget file not found."
    
    with open(widget_path, "r", encoding="utf-8") as f:
        source = f.read()
        
    tree = ast.parse(source)
    top_level_nodes = [
        n for n in tree.body 
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    ]
    
    node_count = len(top_level_nodes)
    assert node_count <= WIDGET_MAX_TOPLEVEL_NODES, (
        f"HARD BOUNDARY EXCEEDED: Widget has {node_count} top-level nodes. "
        f"C47H ratchet locked at {WIDGET_MAX_TOPLEVEL_NODES}. "
        "Create modular service classes and testable modules instead."
    )
