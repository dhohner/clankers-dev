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

    def get_many(self, keys):
        result = {}
        for key in keys:
            entry = self._entries.get(key)
            if entry is None:
                continue
            value, expires_at = entry
            if self._clock() >= expires_at:
                del self._entries[key]
                continue
            if self._clock() < expires_at:
                result[key] = value
        return result

    def set_many(self, items):
        for key, value in items.items():
            expires_at = self._clock() + self._ttl
            self._entries[key] = (value, expires_at)

    def clear(self):
        for key in list(self._entries.keys()):
            del self._entries[key]
