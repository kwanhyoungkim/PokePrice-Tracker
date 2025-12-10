import time

class CacheService:
    def __init__(self):
        self.cache = {}
        self.ttl = 60 * 10  # 10분 캐시

    def get(self, key):
        item = self.cache.get(key)
        if not item:
            return None

        value, expires = item
        if time.time() > expires:
            del self.cache[key]
            return None

        return value

    def set(self, key, value):
        expires = time.time() + self.ttl
        self.cache[key] = (value, expires)