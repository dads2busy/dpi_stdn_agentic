"""
Caching utilities for STDN data layer

This module provides caching mechanisms for expensive operations like
database queries and LLM calls.
"""

import hashlib
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional

# ============================================================================
# Material Cache
# ============================================================================


class MaterialCache:
    """
    Smart cache for material-country mappings.

    Provides disk-based caching with TTL (time-to-live) support to avoid
    redundant database queries and LLM calls.

    Attributes:
        cache_dir: Directory for cache files
        ttl_hours: Time-to-live in hours (default: 24)

    Example:
        >>> cache = MaterialCache(cache_dir="./cache", ttl_hours=24)
        >>>
        >>> # Check cache
        >>> data = cache.get("lithium_2025_2024")
        >>> if data is None:
        ...     data = expensive_query()
        ...     cache.set("lithium_2025_2024", data)
    """

    def __init__(self, cache_dir: str = "./.cache", ttl_hours: int = 24):
        """
        Initialize material cache.

        Args:
            cache_dir: Directory to store cache files
            ttl_hours: Cache TTL in hours (default: 24)
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.ttl = timedelta(hours=ttl_hours)

    def _get_cache_path(self, key: str) -> Path:
        """Get cache file path for a key"""
        # Hash the key to create a safe filename
        key_hash = hashlib.md5(key.encode()).hexdigest()
        return self.cache_dir / f"{key_hash}.json"

    def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache.

        Args:
            key: Cache key

        Returns:
            Cached value if found and not expired, None otherwise
        """
        cache_file = self._get_cache_path(key)

        if not cache_file.exists():
            return None

        try:
            with open(cache_file, "r") as f:
                cache_data = json.load(f)

            # Check expiration
            cached_time = datetime.fromisoformat(cache_data["timestamp"])
            if datetime.now() - cached_time > self.ttl:
                # Expired
                cache_file.unlink()
                return None

            return cache_data["value"]

        except (json.JSONDecodeError, KeyError, ValueError):
            # Corrupted cache file
            cache_file.unlink()
            return None

    def set(self, key: str, value: Any):
        """
        Set value in cache.

        Args:
            key: Cache key
            value: Value to cache (must be JSON-serializable)
        """
        cache_file = self._get_cache_path(key)

        cache_data = {
            "timestamp": datetime.now().isoformat(),
            "key": key,
            "value": value,
        }

        with open(cache_file, "w") as f:
            json.dump(cache_data, f, indent=2, default=str)

    def delete(self, key: str):
        """Delete a cache entry"""
        cache_file = self._get_cache_path(key)
        if cache_file.exists():
            cache_file.unlink()

    def clear(self):
        """Clear all cache entries"""
        for cache_file in self.cache_dir.glob("*.json"):
            cache_file.unlink()

    def get_stats(self) -> Dict:
        """Get cache statistics"""
        cache_files = list(self.cache_dir.glob("*.json"))

        valid_count = 0
        expired_count = 0

        for cache_file in cache_files:
            try:
                with open(cache_file, "r") as f:
                    cache_data = json.load(f)
                cached_time = datetime.fromisoformat(cache_data["timestamp"])

                if datetime.now() - cached_time > self.ttl:
                    expired_count += 1
                else:
                    valid_count += 1
            except Exception:
                expired_count += 1

        return {
            "total_entries": len(cache_files),
            "valid_entries": valid_count,
            "expired_entries": expired_count,
            "cache_dir": str(self.cache_dir),
            "ttl_hours": self.ttl.total_seconds() / 3600,
        }


# ============================================================================
# Public API
# ============================================================================

__all__ = [
    "MaterialCache",
]
