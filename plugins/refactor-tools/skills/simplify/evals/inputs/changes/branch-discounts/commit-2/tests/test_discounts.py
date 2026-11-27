import unittest
from decimal import Decimal

from shop.discounts import bulk_discount, discounted_totals


class DiscountsTest(unittest.TestCase):
    def test_bulk_discount(self):
        self.assertEqual(bulk_discount(100), Decimal("0.10"))
        self.assertEqual(bulk_discount(50), Decimal("0.05"))
        self.assertEqual(bulk_discount(49), Decimal("0"))

    def test_discounted_totals(self):
        lines = [{"price": Decimal("2.00"), "qty": 100}, {"price": Decimal("3.00"), "qty": 10}]
        self.assertEqual(discounted_totals(lines), [Decimal("180.0000"), Decimal("30.00")])
