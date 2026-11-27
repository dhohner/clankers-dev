from decimal import Decimal


def bulk_discount(qty):
    if qty >= 100:
        return Decimal("0.10")
    else:
        if qty >= 50:
            return Decimal("0.05")
        else:
            return Decimal("0")
