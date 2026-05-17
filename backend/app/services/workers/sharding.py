"""Worker sharding and concurrency helpers."""

from __future__ import annotations

import hashlib
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Protocol, TypeVar

T = TypeVar("T", bound="Shardable")


class Shardable(Protocol):
    id: object


@dataclass(frozen=True, slots=True)
class ShardConfig:
    shard_id: int = 0
    shard_count: int = 1

    @property
    def enabled(self) -> bool:
        return self.shard_count > 1


def normalize_shard_config(shard_id: int, shard_count: int) -> ShardConfig:
    """Clamp shard settings to safe values."""
    count = max(1, int(shard_count or 1))
    sid = max(0, int(shard_id or 0))
    if sid >= count:
        sid = sid % count
    return ShardConfig(shard_id=sid, shard_count=count)


def shard_for_key(key: object, shard_count: int) -> int:
    """Return stable shard index for an arbitrary key."""
    count = max(1, int(shard_count or 1))
    digest = hashlib.blake2s(str(key).encode("utf-8"), digest_size=4).digest()
    return int.from_bytes(digest, "big") % count


def belongs_to_shard(key: object, config: ShardConfig) -> bool:
    return shard_for_key(key, config.shard_count) == config.shard_id


def filter_for_shard(items: Iterable[T], config: ShardConfig) -> list[T]:
    """Filter ORM-like rows with an ``id`` attribute to one worker shard."""
    if not config.enabled:
        return list(items)
    return [item for item in items if belongs_to_shard(item.id, config)]
