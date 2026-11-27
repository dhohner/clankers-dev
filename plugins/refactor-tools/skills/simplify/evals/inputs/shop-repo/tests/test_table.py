import unittest

from shop.table import render_header, render_table


class RenderTableTest(unittest.TestCase):
    def test_rows(self):
        html = render_table([{"name": "Bolt", "qty": 3}, {"name": "Nut", "qty": None}])
        self.assertIn("<tr><td>Bolt</td><td>3</td></tr><tr><td>Nut</td><td></td></tr>", html)

    def test_loading(self):
        expected = (
            '<table class="data">'
            + render_header()
            + '<tbody><tr><td colspan="2">Loading</td></tr></tbody></table>'
        )
        self.assertEqual(render_table([], loading=True), expected)
