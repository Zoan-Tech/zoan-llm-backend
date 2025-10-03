import time
import threading
from typing import Dict, Any, Tuple, Optional, TypeVar, Generic
from abc import ABC, abstractmethod
from config.logging import get_logger

logger = get_logger()

T = TypeVar('T')  # Type variable for cached items
K = TypeVar('K')  # Type variable for cache keys


class MemCache(Generic[K, T], ABC):
    """
    Thread-safe base class for in-memory caching with TTL expiration.
    
    Provides common caching functionality that can be reused across different cache implementations.
    Subclasses need to implement key generation and item creation logic.
    """
    
    # Default TTL in seconds (15 minutes)
    DEFAULT_TTL_SECONDS = 15 * 60

    def __init__(self, ttl_seconds: Optional[int] = None, cache_name: str = "MemCache"):
        """
        Initialize the memory cache.
        
        :param ttl_seconds: Time-to-live for cache entries in seconds. Defaults to 15 minutes.
        :param cache_name: Name for logging and identification purposes.
        """
        self.ttl_seconds = ttl_seconds or self.DEFAULT_TTL_SECONDS
        self.cache_name = cache_name
        
        # Main cache storage: {cache_key: (cached_item, timestamp)}
        self._cache: Dict[K, Tuple[T, float]] = {}
        
        # Thread locks for race condition prevention
        self._cache_lock = threading.RLock()  # Reentrant lock for nested operations
        self._cleanup_lock = threading.Lock()  # Simple lock for cleanup operations

    def _is_expired(self, timestamp: float) -> bool:
        """
        Check if a cache entry has expired based on its timestamp.
        
        :param timestamp: The timestamp when the cache entry was created.
        :return: True if expired, False otherwise.
        """
        return time.time() - timestamp > self.ttl_seconds

    def _cleanup_expired_entries(self) -> int:
        """
        Thread-safe removal of expired entries from the cache.
        
        :return: Number of expired entries removed.
        """
        with self._cleanup_lock:
            current_time = time.time()
            
            # First, collect expired keys without holding the main cache lock too long
            with self._cache_lock:
                expired_keys = [
                    key for key, (_, timestamp) in self._cache.items()
                    if current_time - timestamp > self.ttl_seconds
                ]
            
            # Remove expired keys one by one to minimize lock contention
            removed_count = 0
            for key in expired_keys:
                with self._cache_lock:
                    # Double-check the key still exists and is still expired
                    if key in self._cache:
                        _, timestamp = self._cache[key]
                        if current_time - timestamp > self.ttl_seconds:
                            del self._cache[key]
                            removed_count += 1
            
            if removed_count > 0:
                logger.debug(f"[{self.cache_name}] Cleaned up {removed_count} expired cache entries")
            
            return removed_count

    @abstractmethod
    def _generate_cache_key(self, *args, **kwargs) -> K:
        """
        Generate a cache key from the provided arguments.
        Must be implemented by subclasses.
        
        :return: Cache key of type K.
        """
        pass

    @abstractmethod
    def _create_item(self, *args, **kwargs) -> T:
        """
        Create a new item to be cached when cache miss occurs.
        Must be implemented by subclasses.
        
        :return: New item of type T to be cached.
        """
        pass

    def get_or_create(self, *args, **kwargs) -> T:
        """
        Thread-safe get cached item or create new one if not exists or expired.
        Also performs cleanup of expired entries.
        
        :return: The cached or newly created item.
        """
        # Clean up expired entries first (this has its own locking)
        self._cleanup_expired_entries()
        
        cache_key = self._generate_cache_key(*args, **kwargs)
        current_time = time.time()
        
        with self._cache_lock:
            # Check if we have a non-expired cached item
            if cache_key in self._cache:
                cached_item, timestamp = self._cache[cache_key]
                if not self._is_expired(timestamp):
                    return cached_item
                else:
                    # Remove expired entry
                    del self._cache[cache_key]
        
        # Create new item outside of lock to minimize lock time
        new_item = self._create_item(*args, **kwargs)
        
        # Store the new item
        with self._cache_lock:
            # Double-check that another thread hasn't already created this item
            if cache_key in self._cache:
                cached_item, timestamp = self._cache[cache_key]
                if not self._is_expired(timestamp):
                    # Another thread created it, return the existing one
                    return cached_item
            
            # Store our newly created item
            self._cache[cache_key] = (new_item, current_time)
        
        return new_item

    def get(self, cache_key: K) -> Optional[T]:
        """
        Thread-safe get an item from cache by key if it exists and is not expired.
        
        :param cache_key: The cache key to look up.
        :return: The cached item if found and not expired, None otherwise.
        """
        with self._cache_lock:
            if cache_key in self._cache:
                cached_item, timestamp = self._cache[cache_key]
                if not self._is_expired(timestamp):
                    return cached_item
                else:
                    # Remove expired entry
                    del self._cache[cache_key]
                    logger.debug(f"{self.cache_name}: Expired entry removed for key: {cache_key}")
        
        return None

    def put(self, cache_key: K, item: T) -> None:
        """
        Thread-safe put an item in the cache with current timestamp.
        
        :param cache_key: The key to store the item under.
        :param item: The item to cache.
        """
        current_time = time.time()
        with self._cache_lock:
            self._cache[cache_key] = (item, current_time)
        logger.debug(f"{self.cache_name}: Item cached with key: {cache_key}")

    def remove(self, cache_key: K) -> bool:
        """
        Thread-safe remove a specific item from the cache.
        
        :param cache_key: The cache key to remove.
        :return: True if item was removed, False if key didn't exist.
        """
        with self._cache_lock:
            if cache_key in self._cache:
                del self._cache[cache_key]
                logger.debug(f"{self.cache_name}: Removed entry with key: {cache_key}")
                return True
        return False

    def clear(self) -> None:
        """
        Thread-safe clear all entries from the cache.
        """
        with self._cache_lock:
            self._cache.clear()
        logger.debug(f"{self.cache_name}: All cache entries cleared")

    def force_cleanup(self) -> int:
        """
        Manually trigger cleanup of expired cache entries.
        
        :return: Number of expired entries removed.
        """
        return self._cleanup_expired_entries()

    def contains(self, cache_key: K) -> bool:
        """
        Thread-safe check if a non-expired item exists in cache.
        
        :param cache_key: The cache key to check.
        :return: True if key exists and is not expired, False otherwise.
        """
        with self._cache_lock:
            if cache_key in self._cache:
                _, timestamp = self._cache[cache_key]
                return not self._is_expired(timestamp)
        return False

    def get_cache_keys(self) -> list[K]:
        """
        Thread-safe get list of all non-expired cache keys.
        
        :return: List of cache keys for non-expired entries.
        """
        with self._cache_lock:
            current_time = time.time()
            return [
                key for key, (_, timestamp) in self._cache.items()
                if current_time - timestamp <= self.ttl_seconds
            ]

    def get_stats(self) -> Dict[str, Any]:
        """
        Thread-safe get statistics about the current cache state including expiration info.
        
        :return: Dictionary containing cache statistics.
        """
        with self._cache_lock:
            current_time = time.time()
            
            non_expired_count = 0
            expired_count = 0
            ages = []
            cache_keys = []
            
            for key, (_, timestamp) in self._cache.items():
                age_seconds = current_time - timestamp
                ages.append(age_seconds)
                if self._is_expired(timestamp):
                    expired_count += 1
                else:
                    non_expired_count += 1
                    cache_keys.append(key)
        
        return {
            "cache_name": self.cache_name,
            "cache_ttl_seconds": self.ttl_seconds,
            "cache_ttl_minutes": self.ttl_seconds / 60,
            "total_entries": len(self._cache),
            "non_expired_entries": non_expired_count,
            "expired_entries": expired_count,
            "avg_age_seconds": sum(ages) / len(ages) if ages else 0,
            "oldest_age_seconds": max(ages) if ages else 0,
            "non_expired_cache_keys": cache_keys
        }

    @property
    def size(self) -> int:
        """
        Get the current number of entries in the cache.
        
        :return: Number of cache entries.
        """
        return len(self._cache)

    @property
    def is_empty(self) -> bool:
        """
        Check if the cache is empty.
        
        :return: True if cache is empty, False otherwise.
        """
        return len(self._cache) == 0

    def contains_key(self, cache_key: K) -> bool:
        """
        Check if a key exists in the cache (regardless of expiration).
        
        :param cache_key: The key to check.
        :return: True if key exists, False otherwise.
        """
        return cache_key in self._cache

    def get_non_expired_keys(self) -> list[K]:
        """
        Get a list of all non-expired cache keys.
        
        :return: List of non-expired cache keys.
        """
        current_time = time.time()
        return [
            key for key, (_, timestamp) in self._cache.items()
            if not self._is_expired(timestamp)
        ]
