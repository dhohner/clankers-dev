class NoteBook:
    def __init__(self):
        self.notes = []

    def bodies(self):
        return [note["body"] for note in self.notes]
