import unittest
from level_03_boundary_value import is_eligible_for_discount

class TestLevel03(unittest.TestCase):
    def test_over_65(self):
        self.assertTrue(is_eligible_for_discount(66, 0))
        
    def test_exactly_65(self):
        self.assertTrue(is_eligible_for_discount(65, 0))
        
    def test_under_65_but_registered(self):
        self.assertTrue(is_eligible_for_discount(30, 365))
        
    def test_ineligible(self):
        self.assertFalse(is_eligible_for_discount(64, 364))

if __name__ == '__main__':
    unittest.main()
