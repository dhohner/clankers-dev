def slugify(text):
    """Lowercase text and join its words with hyphens."""
    return "-".join(text.casefold().split())
