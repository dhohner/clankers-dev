import unittest
from decimal import Decimal

from shop.returns import refund_amount


class RefundAmountTest(unittest.TestCase):
    def test_restockable_return_pays_the_fee(self):
        self.assertEqual(refund_amount(Decimal("50.00"), damaged=False), Decimal("45.0000"))

    def test_damaged_return_is_refunded_in_full(self):
        self.assertEqual(refund_amount(Decimal("50.00"), damaged=True), Decimal("50.00"))

    def test_negative_amount_is_rejected(self):
        with self.assertRaises(ValueError):
            refund_amount(Decimal("-1"), damaged=False)
