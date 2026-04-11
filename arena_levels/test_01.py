import unittest
from level_01_div_zero import calculate_average

class TestLevel01(unittest.TestCase):
    def test_normal_average(self):
        self.assertEqual(calculate_average([2, 4, 6]), 4.0)

    def test_empty_list(self):
        # Should return 0 or None, but not crash
        result = calculate_average([])
        self.assertIn(result, [0, 0.0, None])

if __name__ == '__main__':
    unittest.main()
