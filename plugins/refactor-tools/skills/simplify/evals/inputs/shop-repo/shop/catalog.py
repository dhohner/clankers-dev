from shop.util.tokens import squash


def product_label(name, sku):
    return f"{squash(name)} ({sku})"
