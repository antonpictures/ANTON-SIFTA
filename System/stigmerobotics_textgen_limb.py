import time
import uuid
import json
import urllib.request
import urllib.error
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from System.stigmerobotics_effector_bridge import EffectorRequest

TEXTGEN_API_URL = "http://127.0.0.1:5000/v1/completions"

def execute_textgen_request(request: "EffectorRequest", now_ts: float) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """
    Executes a TextGen request by hitting the local Oobabooga API.
    If the API is down, returns a clean error receipt (probe-not-trust).
    If it succeeds, returns an OK receipt plus a sensor_echo for PhysicalSpaceReport.
    """
    receipt_trace_id = str(uuid.uuid4())
    
    prompt = request.payload.get("prompt", "")
    max_tokens = request.payload.get("max_tokens", 50)
    
    api_payload = {
        "prompt": prompt,
        "max_tokens": max_tokens
    }
    
    try:
        req = urllib.request.Request(
            TEXTGEN_API_URL, 
            data=json.dumps(api_payload).encode('utf-8'),
            headers={'Content-Type': 'application/json'},
            method='POST'
        )
        with urllib.request.urlopen(req, timeout=5.0) as response:
            result = json.loads(response.read().decode('utf-8'))
            generated_text = result["choices"][0]["text"]
            
        receipt = {
            "ts": now_ts,
            "kind": "effector_receipt",
            "trace_id": receipt_trace_id,
            "request_trace_id": request.trace_id,
            "target_body_id": request.target_body_id,
            "status": "ok",
            "truth_note": "TextGen API generated text successfully.",
            "homeworld_serial": request.homeworld_serial,
            "source_ide": "effector_daemon"
        }
        
        sensor_echo = {
            "ts": now_ts + 0.1,
            "kind": "desk_telemetry_radar",
            "body_id": request.target_body_id,
            "payload": {
                "generated_text": generated_text,
                "model_backend": "textgen_webui"
            },
            "distance_m": 0.0,
            "confidence": 1.0,
            "truth_label": "OBSERVED",
            "homeworld_serial": request.homeworld_serial
        }
        
    except Exception as e:
        receipt = {
            "ts": now_ts,
            "kind": "effector_receipt",
            "trace_id": receipt_trace_id,
            "request_trace_id": request.trace_id,
            "target_body_id": request.target_body_id,
            "status": "error",
            "truth_note": f"TextGen API failed or unreachable: {str(e)}",
            "homeworld_serial": request.homeworld_serial,
            "source_ide": "effector_daemon"
        }
        sensor_echo = None
        
    return receipt, sensor_echo
