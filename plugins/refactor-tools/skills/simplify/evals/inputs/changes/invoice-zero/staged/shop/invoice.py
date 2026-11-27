from decimal import Decimal

from shop.util.money import format_currency, round_money


def format_invoice_total(lines):
    total = sum((line["amount"] for line in lines), Decimal("0"))
    if round_money(total) == 0:
        return "$0.00"
    return format_currency(total)


def format_refund(amount):
    return "Refund " + format_currency(amount)
