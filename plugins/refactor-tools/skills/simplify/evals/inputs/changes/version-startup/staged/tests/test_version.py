import unittest

from shop.version import version_label


class VersionLabelTest(unittest.TestCase):
    def test_label_names_the_build(self):
        label = version_label("shop")
        self.assertTrue(label.startswith("shop ("))
        self.assertTrue(label.endswith(")"))
