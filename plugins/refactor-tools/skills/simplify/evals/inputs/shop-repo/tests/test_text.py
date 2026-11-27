import unittest

from shop.util.text import slugify


class SlugifyTest(unittest.TestCase):
    def test_slugify(self):
        self.assertEqual(slugify("  Hex   Bolt "), "hex-bolt")
