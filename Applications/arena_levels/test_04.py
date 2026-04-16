import unittest
from level_04_exception_swallow import parse_config

class TestLevel04(unittest.TestCase):
    def test_valid_json(self):
        self.assertEqual(parse_config('{"key": "value"}'), {"key": "value"})

    def test_invalid_json_raises_value_error(self):
        with self.assertRaises(ValueError):
            parse_config('{"key": "value", }')

if __name__ == '__main__':
    unittest.main()
