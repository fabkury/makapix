"""Test vault storage utilities."""

import hashlib
from uuid import UUID

import pytest

from app.vault import compute_storage_shard, hash_artwork_id


class TestComputeStorageShard:
    """Tests for compute_storage_shard function."""

    def test_returns_correct_format(self):
        """Test that compute_storage_shard returns 'xx/yy/zz' format."""
        storage_key = UUID("a1b2c3d4-e5f6-7890-abcd-ef1234567890")
        result = compute_storage_shard(storage_key)

        # Should be exactly 8 characters: "xx/yy/zz"
        assert len(result) == 8
        # Should have slashes at correct positions
        assert result[2] == "/"
        assert result[5] == "/"
        # Each chunk should be 2 hex characters
        chunks = result.split("/")
        assert len(chunks) == 3
        for chunk in chunks:
            assert len(chunk) == 2
            # Verify each chunk is valid hex
            int(chunk, 16)

    def test_matches_hash_artwork_id(self):
        """Test that compute_storage_shard uses the same hash as hash_artwork_id."""
        storage_key = UUID("12345678-1234-5678-1234-567812345678")

        # Get the full hash
        full_hash = hash_artwork_id(storage_key)

        # Compute the shard
        shard = compute_storage_shard(storage_key)

        # Shard should be derived from first 6 chars of hash
        expected_shard = f"{full_hash[0:2]}/{full_hash[2:4]}/{full_hash[4:6]}"
        assert shard == expected_shard

    def test_deterministic(self):
        """Test that compute_storage_shard returns the same result for the same input."""
        storage_key = UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")

        result1 = compute_storage_shard(storage_key)
        result2 = compute_storage_shard(storage_key)

        assert result1 == result2

    def test_different_keys_different_shards(self):
        """Test that different storage keys produce different shards (with high probability)."""
        key1 = UUID("11111111-1111-1111-1111-111111111111")
        key2 = UUID("22222222-2222-2222-2222-222222222222")

        shard1 = compute_storage_shard(key1)
        shard2 = compute_storage_shard(key2)

        assert shard1 != shard2

    def test_known_value(self):
        """Test against a known hash value for regression testing."""
        # Use a specific UUID and verify the expected shard
        storage_key = UUID("00000000-0000-0000-0000-000000000000")

        # Compute expected hash manually
        expected_hash = hashlib.sha256(str(storage_key).encode()).hexdigest()
        expected_shard = (
            f"{expected_hash[0:2]}/{expected_hash[2:4]}/{expected_hash[4:6]}"
        )

        result = compute_storage_shard(storage_key)
        assert result == expected_shard
