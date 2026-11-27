import unittest
from decimal import Decimal

from shop.shipping import shipping_fee


class ShippingFeeTest(unittest.TestCase):
    def test_fees(self):
        self.assertEqual(shipping_fee(11, True), Decimal("25.00"))
        self.assertEqual(shipping_fee(10, True), Decimal("15.00"))
        self.assertEqual(shipping_fee(11, False), Decimal("12.00"))
        self.assertEqual(shipping_fee(10, False), Decimal("6.00"))
