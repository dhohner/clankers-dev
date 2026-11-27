import unittest

from shop.cache_store import CacheStore


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


class CacheStoreTest(unittest.TestCase):
    def setUp(self):
        self.clock = FakeClock()
        self.store = CacheStore(10, clock=self.clock)

    def test_get_expires(self):
        self.store.set("a", 1)
        self.assertEqual(self.store.get("a"), 1)
        self.clock.now = 10
        self.assertIsNone(self.store.get("a"))

    def test_clear(self):
        self.store.set("a", 1)
        self.store.clear()
        self.assertIsNone(self.store.get("a"))
