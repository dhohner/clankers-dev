from decimal import Decimal

RESTOCKING_FEE = Decimal("0.10")


def refund_amount(amount, damaged):
    if amount < 0:
        raise ValueError("bad input")
    restockable = not damaged
    if restockable:
        return amount - amount * RESTOCKING_FEE
    else:
        return amount
