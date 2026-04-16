import pytest
import os
import sys

# Ensure the parent directory is in the path to import thermal_management
sys.path.insert(0, os.path.dirname(__file__))

def test_thermal_safety_limit():
    from thermal_management import monitor_core_temp
    # Instead of running the infinite loop, we will just parse the file to evaluate the limit statically,
    # OR import the module and inspect the variable if it's extracted, but monitor_core_temp holds it inside.
    # WAIT! The snippet provided by the user had max_safe_temp inside the function `monitor_core_temp`!
    
    # If it's inside the function, we have to parse the AST or run it briefly.
    # Actually, a better way is to read the file or monkeypatch. Let's do a simple AST parse
    # to find max_safe_temp assigned value.
    import ast
    with open(os.path.join(os.path.dirname(__file__), "thermal_management.py"), "r") as f:
        tree = ast.parse(f.read())
        
    found_limit = None
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == 'max_safe_temp':
                    # Extract the value
                    if isinstance(node.value, ast.Constant):
                        found_limit = node.value.value
                        
    assert found_limit is not None, "max_safe_temp variable is missing!"
    assert found_limit < 50.0, f"CRITICAL: max_safe_temp is {found_limit}C! Anything over 50.0C causes runaway meltdowns!"
