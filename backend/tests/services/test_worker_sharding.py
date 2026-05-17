from dataclasses import dataclass

from app.services.workers.sharding import filter_for_shard, normalize_shard_config, shard_for_key


@dataclass
class Row:
    id: str


def test_shard_for_key_is_stable_and_bounded():
    first = shard_for_key("device-a", 4)
    assert first == shard_for_key("device-a", 4)
    assert 0 <= first < 4


def test_filter_for_shard_partitions_without_duplicates():
    rows = [Row(f"device-{i}") for i in range(20)]
    shards = [filter_for_shard(rows, normalize_shard_config(i, 4)) for i in range(4)]
    flattened = [row.id for shard in shards for row in shard]
    assert sorted(flattened) == sorted(row.id for row in rows)
    assert len(flattened) == len(set(flattened))


def test_invalid_shard_id_wraps_safely():
    config = normalize_shard_config(5, 4)
    assert config.shard_id == 1
    assert config.shard_count == 4
