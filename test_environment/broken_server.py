def calculate_pressure(sensor_data):
    # Bug: Division by zero if sensor_data is empty
    average = sum(sensor_data) / len(sensor_data)
    
    # Bug: Logic error - pressure cannot be negative in this system
    if average < 0:
        return "Normal" # Should be an error state
    return average
import threading
import time

class SensorCounter:
    def __init__(self):
        self.count = 0

    def increment(self):
        # Bug: Race condition. Read, modify, write is not atomic.
        current = self.count
        time.sleep(0.0001) # Simulate some processing time
        self.count = current + 1

def run_sensors():
    counter = SensorCounter()
    threads = []
    for _ in range(100):
        t = threading.Thread(target=counter.increment)
        threads.append(t)
        t.start()
        
    for t in threads:
        t.join()
        
    return counter.count
def check_temperature_limit(temp):
    # Bug: Fails when input is exactly at the limit (100)
    # The specification says temperature must be strictly less than 100 to be safe.
    if temp > 100:
        return "Critical"
    elif temp > 80:
        return "Warning"
    else:
        return "Safe"
import json

@app.route("/api/v1/status")
def status():
    # Intentionally broken: unterminated string literal
    status_msg = "All systems online. The swarm architecture is active."
    return {"status": status_msg}

def parse_sensor_config(config_string):
    try:
        config = json.loads(config_string)
        return config['sensor_id'], config['threshold']
    except:
        # Bug: Naked except swallows all errors, including syntax errors, 
        # keyboard interrupts, and missing keys, returning a dangerous default.
        pass
    
    return "default_sensor", 100
import unittest
import json
from broken import parse_sensor_config

class TestSensorConfig(unittest.TestCase):
    def test_valid_config(self):
        config_str = '{"sensor_id": "temp_01", "threshold": 85}'
        sensor_id, threshold = parse_sensor_config(config_str)
        self.assertEqual(sensor_id, "temp_01")
        self.assertEqual(threshold, 85)

    def test_invalid_json(self):
        config_str = '{"sensor_id": "temp_01", "threshold": 85' # Missing closing brace
        # Should raise json.JSONDecodeError instead of swallowing it
        with self.assertRaises(json.JSONDecodeError):
            parse_sensor_config(config_str)
            
    def test_missing_key(self):
        config_str = '{"sensor_id": "temp_01"}' # Missing threshold
        # Should raise KeyError
        with self.assertRaises(KeyError):
            parse_sensor_config(config_str)

if __name__ == '__main__':
    unittest.main()
import unittest
from broken import check_temperature_limit

class TestTemperatureLimit(unittest.TestCase):
    def test_safe_temp(self):
        self.assertEqual(check_temperature_limit(50), "Safe")
def calculate_pressure(data):
    if not data:
        return None
    
    positive_values = [value for value in data if value > 0]
    
    if not positive_values:
        return 0
    
    return sum(positive_values) / len(positive_values)
    avg_positive_pressure = sum(positive_values) / len(positive_values)
    return avg_positive_pressure

class TestCalculatePressure(unittest.TestCase):
        
    def test_empty_data(self):
        self.assertIsNone(calculate_pressure([]))
    
    def test_negative_values(self):
        pressures = [10, -20, 30]
        # Assuming the function handles negative values by ignoring them and calculating average from remaining positive numbers
        self.assertEqual(calculate
