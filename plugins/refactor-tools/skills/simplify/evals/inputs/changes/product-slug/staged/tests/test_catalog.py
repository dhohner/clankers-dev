import unittest

from shop.catalog import product_label, product_slug, product_slugs


class CatalogTest(unittest.TestCase):
    def test_product_label(self):
        self.assertEqual(product_label(" Hex  Bolt ", "HB-6"), "Hex Bolt (HB-6)")

    def test_product_slug(self):
        self.assertEqual(product_slug("  Hex   Bolt "), "hex-bolt")

    def test_product_slugs(self):
        self.assertEqual(product_slugs(["Hex Bolt", "Wing Nut"]), ["hex-bolt", "wing-nut"])
