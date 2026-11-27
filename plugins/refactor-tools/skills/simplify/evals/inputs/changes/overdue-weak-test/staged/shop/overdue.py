def first_overdue(invoices, today):
    result = None
    for invoice in invoices:
        if invoice["due"] < today and not invoice["paid"]:
            if result is None or invoice["due"] < result["due"]:
                result = invoice
    return result


def overdue_total(invoices, today):
    total = 0
    for invoice in invoices:
        if invoice["due"] < today:
            if not invoice["paid"]:
                total = total + invoice["amount"]
    return total
