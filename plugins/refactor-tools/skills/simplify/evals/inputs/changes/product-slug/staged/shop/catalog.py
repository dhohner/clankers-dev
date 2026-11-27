from shop.util.tokens import squash


def product_label(name, sku):
    return f"{squash(name)} ({sku})"


def product_slug(name):
    return "-".join(name.lower().split())


def product_slugs(names):
    slugs = []
    for name in names:
        slugs.append("-".join(name.lower().split()))
    return slugs
