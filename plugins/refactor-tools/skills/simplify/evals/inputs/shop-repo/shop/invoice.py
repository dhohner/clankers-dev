from decimal import Decimal

from shop.util.money import format_currency


def format_invoice_total(lines):
    total = sum((line["amount"] for line in lines), Decimal("0"))
    return format_currency(total)


def format_refund(amount):
    return "Refund " + format_currency(amount)
