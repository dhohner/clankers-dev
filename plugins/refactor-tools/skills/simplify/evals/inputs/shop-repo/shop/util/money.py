from decimal import ROUND_HALF_EVEN, Decimal


def round_money(amount):
    return Decimal(amount).quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN)


def format_currency(amount):
    return f"${round_money(amount):,.2f}"
