# In-memory datastore with TTL (absolute timestamp). Async-safe via single lock.

import time
import asyncio
from typing import Optional, Dict, Tuple, List


class DataStore:
    def __init__(self):
        # key -> (value: bytes, expires_at: Optional[float])
        self._data: Dict[bytes, Tuple[bytes, Optional[float]]] = {}
        self._lock = asyncio.Lock()

    def _is_expired_unlocked(self, key: bytes) -> bool:
        item = self._data.get(key)
        if item is None:
            return False
        _, exp = item
        return (exp is not None) and (exp < time.time())

    async def set(self, key: bytes, value: bytes, ex_seconds: Optional[float] = None,
                  keep_ttl: bool = False, nx: bool = False, xx: bool = False) -> bool:
        async with self._lock:
            exists = key in self._data and not self._is_expired_unlocked(key)
            if nx and exists:
                return False
            if xx and not exists:
                return False

            prev_exp = self._data.get(key, (b"", None))[1] if exists else None
            expiry = prev_exp if (keep_ttl and exists) else None
            if ex_seconds is not None:
                expiry = time.time() + ex_seconds
            self._data[key] = (value, expiry)
            return True

    async def get(self, key: bytes) -> Optional[bytes]:
        async with self._lock:
            if self._is_expired_unlocked(key):
                self._data.pop(key, None)
                return None
            item = self._data.get(key)
            return None if item is None else item[0]

    async def ttl(self, key: bytes) -> int:
        async with self._lock:
            if self._is_expired_unlocked(key):
                self._data.pop(key, None)
                return -2
            item = self._data.get(key)
            if item is None:
                return -2
            _, exp = item
            if exp is None:
                return -1
            remaining = int(exp - time.time())
            if remaining < 0:
                self._data.pop(key, None)
                return -2
            return remaining

    async def expire(self, key: bytes, seconds: int) -> int:
        async with self._lock:
            if self._is_expired_unlocked(key):
                self._data.pop(key, None)
                return 0
            if key not in self._data:
                return 0
            val, _ = self._data[key]
            self._data[key] = (val, time.time() + seconds)
            return 1

    async def pexpire(self, key: bytes, milliseconds: int) -> int:
        async with self._lock:
            if self._is_expired_unlocked(key):
                self._data.pop(key, None)
                return 0
            if key not in self._data:
                return 0
            val, _ = self._data[key]
            self._data[key] = (val, time.time() + milliseconds / 1000.0)
            return 1

    async def del_keys(self, keys: List[bytes]) -> int:
        async with self._lock:
            cnt = 0
            for k in keys:
                if self._is_expired_unlocked(k):
                    self._data.pop(k, None)
                    continue
                if k in self._data:
                    self._data.pop(k, None)
                    cnt += 1
            return cnt

    async def exists(self, keys: List[bytes]) -> int:
        async with self._lock:
            cnt = 0
            for k in keys:
                if self._is_expired_unlocked(k):
                    self._data.pop(k, None)
                    continue
                if k in self._data:
                    cnt += 1
            return cnt

    async def cleanup_task(self, interval: float = 1.0):
        try:
            while True:
                await asyncio.sleep(interval)
                now = time.time()
                async with self._lock:
                    expired = [k for k, (_, exp) in self._data.items() if exp is not None and exp < now]
                    for k in expired:
                        self._data.pop(k, None)
        except asyncio.CancelledError:
            pass
