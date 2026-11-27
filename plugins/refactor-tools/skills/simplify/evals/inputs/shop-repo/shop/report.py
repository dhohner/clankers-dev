def total_quantity(orders):
    return sum(order["qty"] for order in orders)
