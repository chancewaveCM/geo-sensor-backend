"""Unit tests for SimpleCache."""

import time
from unittest.mock import patch

from app.core.cache import SimpleCache


class TestSimpleCache:
    """Tests for SimpleCache TTL-based caching."""

    def test_set_and_get_within_ttl(self) -> None:
        """Test setting and getting value within TTL."""
        cache = SimpleCache()
        cache.set("key1", "value1", ttl=60)

        result = cache.get("key1")
        assert result == "value1"

    def test_get_after_ttl_expiry(self) -> None:
        """Test that expired entries return None."""
        cache = SimpleCache()
        cache.set("key1", "value1", ttl=1)  # 1 second TTL

        # Wait for expiry
        time.sleep(1.1)

        result = cache.get("key1")
        assert result is None

    def test_get_after_ttl_expiry_removes_entry(self) -> None:
        """Test that accessing expired entry removes it from store."""
        cache = SimpleCache()
        cache.set("key1", "value1", ttl=1)

        time.sleep(1.1)
        cache.get("key1")

        # Entry should be removed from internal store
        assert "key1" not in cache._store

    def test_get_nonexistent_key(self) -> None:
        """Test getting non-existent key returns None."""
        cache = SimpleCache()

        result = cache.get("nonexistent")
        assert result is None

    def test_invalidate_with_exact_match(self) -> None:
        """Test invalidate with exact key match."""
        cache = SimpleCache()
        cache.set("key1", "value1")
        cache.set("key2", "value2")

        count = cache.invalidate("key1")

        assert count == 1
        assert cache.get("key1") is None
        assert cache.get("key2") == "value2"

    def test_invalidate_with_prefix_pattern(self) -> None:
        """Test invalidate with prefix pattern."""
        cache = SimpleCache()
        cache.set("user:1", "data1")
        cache.set("user:2", "data2")
        cache.set("user:3", "data3")
        cache.set("product:1", "product_data")

        count = cache.invalidate("user")

        assert count == 3
        assert cache.get("user:1") is None
        assert cache.get("user:2") is None
        assert cache.get("user:3") is None
        assert cache.get("product:1") == "product_data"

    def test_invalidate_doesnt_affect_unrelated_keys(self) -> None:
        """Test that invalidate doesn't remove unrelated keys."""
        cache = SimpleCache()
        cache.set("campaign:1", "data1")
        cache.set("campaign:2", "data2")
        cache.set("competitive:1", "comp_data")

        cache.invalidate("campaign")

        assert cache.get("competitive:1") == "comp_data"

    def test_clear_removes_everything(self) -> None:
        """Test that clear removes all entries."""
        cache = SimpleCache()
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.set("key3", "value3")

        cache.clear()

        assert cache.get("key1") is None
        assert cache.get("key2") is None
        assert cache.get("key3") is None
        assert len(cache._store) == 0

    def test_default_ttl(self) -> None:
        """Test that default TTL is 300 seconds (5 minutes)."""
        cache = SimpleCache()

        with patch('time.time', return_value=1000.0):
            cache.set("key1", "value1")  # Default TTL

        # Check internal expiry time
        _, expires_at = cache._store["key1"]
        assert expires_at == 1300.0  # 1000 + 300

    def test_custom_ttl(self) -> None:
        """Test setting custom TTL."""
        cache = SimpleCache()

        with patch('time.time', return_value=1000.0):
            cache.set("key1", "value1", ttl=600)

        _, expires_at = cache._store["key1"]
        assert expires_at == 1600.0  # 1000 + 600

    def test_overwrite_existing_key(self) -> None:
        """Test that setting an existing key overwrites it."""
        cache = SimpleCache()
        cache.set("key1", "original")
        cache.set("key1", "updated")

        result = cache.get("key1")
        assert result == "updated"

    def test_cache_different_types(self) -> None:
        """Test caching different data types."""
        cache = SimpleCache()

        cache.set("string", "text")
        cache.set("int", 42)
        cache.set("dict", {"key": "value"})
        cache.set("list", [1, 2, 3])

        assert cache.get("string") == "text"
        assert cache.get("int") == 42
        assert cache.get("dict") == {"key": "value"}
        assert cache.get("list") == [1, 2, 3]

    def test_invalidate_returns_count(self) -> None:
        """Test that invalidate returns correct count of removed items."""
        cache = SimpleCache()
        cache.set("prefix:1", "a")
        cache.set("prefix:2", "b")
        cache.set("prefix:3", "c")

        count = cache.invalidate("prefix")
        assert count == 3

    def test_invalidate_nonexistent_pattern(self) -> None:
        """Test invalidating non-existent pattern returns 0."""
        cache = SimpleCache()
        cache.set("key1", "value1")

        count = cache.invalidate("nonexistent")
        assert count == 0
