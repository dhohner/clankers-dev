import unittest
from decimal import Decimal

from shop.invoice import format_invoice_total, format_refund


class InvoiceTest(unittest.TestCase):
    def test_total(self):
        lines = [{"amount": Decimal("1200.50")}, {"amount": Decimal("0.25")}]
        self.assertEqual(format_invoice_total(lines), "$1,200.75")

    def test_small_credit_total(self):
        self.assertEqual(format_invoice_total([{"amount": Decimal("-0.004")}]), "$0.00")

    def test_refund(self):
        self.assertEqual(format_refund(Decimal("5")), "Refund $5.00")
