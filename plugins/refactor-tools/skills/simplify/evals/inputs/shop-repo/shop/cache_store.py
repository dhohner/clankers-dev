import time


class CacheStore:
    def __init__(self, ttl_seconds, clock=time.monotonic):
        self._ttl = ttl_seconds
        self._clock = clock
        self._entries = {}

    def get(self, key):
        entry = self._entries.get(key)
        if entry == None:
            return None
        value, expires_at = entry
        if self._clock() >= expires_at:
            del self._entries[key]
            return None
        return value

    def set(self, key, value):
        self._entries[key] = (value, self._clock() + self._ttl)

    def clear(self):
        for key in list(self._entries.keys()):
            del self._entries[key]
