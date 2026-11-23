import unittest
from mouse import HorizontalLimit


class ManualInputTest(unittest.TestCase):
    def test_physical_movement_only(self):
        limit = HorizontalLimit([(1,"move",100,0)],20)
        self.assertEqual(limit.apply(0,50),20)
        self.assertEqual(limit.apply(.5,3),0)
        self.assertEqual(limit.apply(1,0),0)
        self.assertEqual(limit.apply(1,-4),0)
        self.assertEqual(limit.apply(1,7),7)
        self.assertEqual(limit.apply(1,200),93)
        self.assertEqual(limit.apply(1,-200),-40)
