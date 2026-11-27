import unittest

from shop.report import total_quantity


class ReportTest(unittest.TestCase):
    def test_total_quantity(self):
        self.assertEqual(total_quantity([{"qty": 2}, {"qty": 3}]), 5)
