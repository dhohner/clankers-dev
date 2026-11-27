import re


class NoteBook:
    def __init__(self):
        self.notes = []

    def bodies(self):
        return [note["body"] for note in self.notes]

    def add_note(self, text, tags=()):
        body = re.sub(r"\s+", " ", text).strip()
        if not body:
            raise ValueError("note text is empty")
        clean_tags = []
        for tag in tags:
            clean_tags.append(re.sub(r"\s+", " ", tag).strip().lower())
        self.notes.append({"body": body, "tags": clean_tags})
