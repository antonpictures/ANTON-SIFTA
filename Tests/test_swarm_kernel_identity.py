import pytest
from System.swarm_kernel_identity import (
    owner_silicon, 
    owner_name, 
    ai_default_name, 
    is_owner_machine,
    owner_genesis_present
)

def test_kernel_identity_accessors():
    """Verify that the module correctly parses the owner genesis block."""
    assert owner_genesis_present(), "Owner genesis should be mocked or present"
    
    silicon = owner_silicon()
    assert silicon == "GTH4921YP3", f"Expected GTH4921YP3, got {silicon}"
    
    name = owner_name()
    assert name == "Ioan George Anton", f"Expected Ioan George Anton, got {name}"
    
    ai_name = ai_default_name()
    assert ai_name == "Alice", f"Expected Alice default, got {ai_name}"
    
    assert is_owner_machine(silicon), "is_owner_machine() should return True for matched silicon"
    assert not is_owner_machine("INVALID_M5_SERIAL"), "is_owner_machine() failed rejection"
