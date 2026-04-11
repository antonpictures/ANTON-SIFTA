import json

def parse_config(json_string):
    """
    Parses a JSON configuration.
    Should return a dictionary if successful.
    Should raise ValueError if the JSON is malformed.
    """
    try:
        data = json.loads(json_string)
        return data
    except json.JSONDecodeError as e:
        # Re-raise the exception as ValueError as required
        raise ValueError(f"Malformed JSON configuration: {e}")