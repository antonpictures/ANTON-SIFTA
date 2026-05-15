import time
import json
import uuid
from unittest.mock import patch, MagicMock
from System.stigmerobotics_effector_bridge import EffectorRequest, execute_request_stub

def test_textgen_limb_offline():
    """Proves the limb acts as a probe and safely errors when TextGen is offline."""
    req = EffectorRequest(
        trace_id=str(uuid.uuid4()),
        target_body_id="textgen_limb",
        action_type="generate_text",
        payload={"prompt": "Hello", "max_tokens": 10},
        source_ide="test_suite",
        homeworld_serial="GTH4921YP3",
        ts=time.time()
    )
    
    # Force connection error
    with patch("urllib.request.urlopen", side_effect=Exception("Connection refused")):
        receipt, echo = execute_request_stub(req, time.time())
        
    assert receipt["status"] == "error"
    assert "failed or unreachable" in receipt["truth_note"]
    assert echo is None  # No physical space report if it didn't happen

def test_textgen_limb_online():
    """Proves the limb generates text and grounds it in the physical space report."""
    req = EffectorRequest(
        trace_id=str(uuid.uuid4()),
        target_body_id="textgen_limb",
        action_type="generate_text",
        payload={"prompt": "Hello", "max_tokens": 10},
        source_ide="test_suite",
        homeworld_serial="GTH4921YP3",
        ts=time.time()
    )
    
    mock_response = MagicMock()
    mock_response.read.return_value = json.dumps({
        "choices": [{"text": " World!"}]
    }).encode("utf-8")
    
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.return_value.__enter__.return_value = mock_response
        receipt, echo = execute_request_stub(req, time.time())
        
    assert receipt["status"] == "ok"
    assert receipt["target_body_id"] == "textgen_limb"
    
    # Grounding proof
    assert echo is not None
    assert echo["truth_label"] == "OBSERVED"
    assert echo["payload"]["generated_text"] == " World!"
