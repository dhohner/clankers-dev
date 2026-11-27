import subprocess

BUILD = subprocess.run(
    ["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True
).stdout.strip()


def version_label(name):
    return f"{name} ({BUILD})"
