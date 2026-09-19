import time
from typing import Any, Dict, Optional, Tuple

class TTLCache:
    """
    Thread-safe-styled, standard in-memory Key-Value pair cache supporting Time-To-Live (TTL) evictions.
    Expired entries are garbage cleaned either during accesses or manual checks.
    """
    def __init__(self, default_ttl_seconds: int = 3600):
        self.default_ttl = default_ttl_seconds
        # Mapping format inside index store: { key: (cached_value, absolute_expiry_epoch_time) }
        self._store: Dict[Any, Tuple[Any, float]] = {}

    def set(self, key: Any, value: Any, ttl: Optional[float] = None) -> None:
        """
        Stores key-value pair with designated duration parameters.
        """
        duration = ttl if ttl is not None else self.default_ttl
        expiry_epoch = time.time() + duration
        self._store[key] = (value, expiry_epoch)

    def get(self, key: Any) -> Any:
        """
        Retrieves cache objects. Returns None if key has expired or is missing.
        """
        if key not in self._store:
            return None
            
        value, expiry_epoch = self._store[key]
        if time.time() > expiry_epoch:
            # Automatic lazy deletion of expired fields
            self.delete(key)
            return None
            
        return value

    def delete(self, key: Any) -> None:
        """
        Safely clears designated cache objects.
        """
        if key in self._store:
            del self._store[key]

    def clear(self) -> None:
        """
        Clears all cache memories completely.
        """
        self._store.clear()

    def is_expired(self, key: Any) -> bool:
        """
        Returns True if the designated key is expired or missing.
        """
        if key not in self._store:
            return True
        _, expiry_epoch = self._store[key]
        return time.time() > expiry_epoch

# Define global cache client for caching pipeline tasks
cache = TTLCache()
