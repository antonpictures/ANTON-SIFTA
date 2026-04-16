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
    except Exception as e:
        # BUG: We are swallowing the exception and returning None
        # It should reraise as ValueError
        print("Error parsing json:", e)
        return None
