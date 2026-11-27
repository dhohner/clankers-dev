import unittest
from datetime import date

from shop.overdue import first_overdue, overdue_total


class OverdueTest(unittest.TestCase):
    def test_nothing_overdue_when_all_paid(self):
        invoices = [{"due": date(2026, 1, 1), "paid": True, "amount": 5}]
        self.assertIsNone(first_overdue(invoices, date(2026, 2, 1)))
        self.assertEqual(overdue_total(invoices, date(2026, 2, 1)), 0)
