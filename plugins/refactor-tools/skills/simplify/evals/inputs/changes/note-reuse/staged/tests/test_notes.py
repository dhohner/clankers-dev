import unittest

from shop.notes import NoteBook


class NoteBookTest(unittest.TestCase):
    def test_add_note_normalizes_text_and_tags(self):
        book = NoteBook()
        book.add_note("  ship\n the   order ", tags=[" Urgent  Today "])
        self.assertEqual(book.notes, [{"body": "ship the order", "tags": ["urgent today"]}])

    def test_add_note_rejects_blank_text(self):
        with self.assertRaises(ValueError):
            NoteBook().add_note(" \t ")
