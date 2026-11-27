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
    first = raw.get("first_name")
    if isinstance(first, str) and first.strip():
        first = first.strip()
    else:
        first = ""
    last = raw.get("last_name")
    if isinstance(last, str) and last.strip():
        last = last.strip()
    else:
        last = ""
    if first and last:
        display_name = f"{first} {last}"
    elif first or last:
        display_name = first or last
    else:
        display_name = "Anonymous"
    nickname = raw.get("nickname")
    if isinstance(nickname, str) and nickname.strip():
        display_name = nickname.strip()
    birthday = raw.get("birthday")
    if isinstance(birthday, str) and birthday.strip():
        birthday = birthday.strip()
    else:
        birthday = None
    return {
        "id": raw["id"],
        "display_name": display_name,
        "birthday": birthday,
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
