from decimal import Decimal

from shop.util.money import round_money

GUEST_MARKUP = Decimal("1.10")


def guest_price(base):
    return round_money(base * GUEST_MARKUP)
