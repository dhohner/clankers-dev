def read_string(raw, key, default=""):
    value = raw.get(key)
    if isinstance(value, str) and value.strip():
        return value.strip()
    return default


def format_display_name(first, last):
    if first and last:
        return f"{first} {last}"
    return first or last or "Anonymous"


def fetch_user_profile(raw):
    first = read_string(raw, "first_name")
    last = read_string(raw, "last_name")
    return {
        "id": raw["id"],
        "display_name": format_display_name(first, last),
        "birthday": read_string(raw, "birthday", None),
    }


def list_user_emails(users):
    emails = []
    for user in users:
        if user.get("email") != None:
            emails.append(user.get("email"))
    return emails


def describe_user(user):
    if user.get("active"):
        if user.get("admin"):
            return "active admin"
        else:
            return "active user"
    else:
        return "inactive user"
