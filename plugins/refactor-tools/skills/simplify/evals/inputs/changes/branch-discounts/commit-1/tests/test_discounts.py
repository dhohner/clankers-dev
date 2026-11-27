import unittest
from decimal import Decimal

from shop.discounts import bulk_discount


class DiscountsTest(unittest.TestCase):
    def test_bulk_discount(self):
        self.assertEqual(bulk_discount(100), Decimal("0.10"))
        self.assertEqual(bulk_discount(50), Decimal("0.05"))
        self.assertEqual(bulk_discount(49), Decimal("0"))
