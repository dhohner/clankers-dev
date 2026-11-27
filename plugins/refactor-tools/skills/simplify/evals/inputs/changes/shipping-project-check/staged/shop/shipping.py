from decimal import Decimal


def shipping_fee(weight_kg, express):
    if express:
        if weight_kg > 10:
            return Decimal("25.00")
        else:
            return Decimal("15.00")
    else:
        if weight_kg > 10:
            return Decimal("12.00")
        else:
            return Decimal("6.00")
