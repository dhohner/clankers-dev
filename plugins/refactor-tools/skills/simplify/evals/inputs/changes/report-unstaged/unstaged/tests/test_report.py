import unittest

from shop.report import average_quantity, count_by_status, total_quantity


class ReportTest(unittest.TestCase):
    def test_total_quantity(self):
        self.assertEqual(total_quantity([{"qty": 2}, {"qty": 3}]), 5)

    def test_average_quantity(self):
        self.assertEqual(average_quantity([{"qty": 2}, {"qty": 4}]), 3)
        self.assertEqual(average_quantity([]), 0)

    def test_count_by_status(self):
        orders = [{"status": "open"}, {"status": "paid"}, {"status": "open"}]
        self.assertEqual(count_by_status(orders), {"open": 2, "paid": 1})
