def total_quantity(orders):
    return sum(order["qty"] for order in orders)


def average_quantity(orders):
    if len(orders) == 0:
        return 0
    else:
        total = 0
        for order in orders:
            total = total + order["qty"]
        return total / len(orders)


def count_by_status(orders):
    counts = {}
    for order in orders:
        status = order["status"]
        if status in counts:
            counts[status] = counts[status] + 1
        else:
            counts[status] = 1
    return counts
