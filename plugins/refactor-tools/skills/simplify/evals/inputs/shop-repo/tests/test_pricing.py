import unittest
from decimal import Decimal

from shop.pricing import guest_price


class PricingTest(unittest.TestCase):
    def test_guest_price(self):
        self.assertEqual(guest_price(Decimal("10.00")), Decimal("11.00"))
