from decimal import Decimal


def bulk_discount(qty):
    if qty >= 100:
        return Decimal("0.10")
    else:
        if qty >= 50:
            return Decimal("0.05")
        else:
            return Decimal("0")


def discounted_totals(lines):
    totals = []
    for line in lines:
        discount = bulk_discount(line["qty"])
        totals.append(line["price"] * line["qty"] - line["price"] * line["qty"] * discount)
    return totals
