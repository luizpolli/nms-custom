#!/usr/bin/env python3
"""Seed BulkstatsCounterCatalog with one row per StarOS disc-reason-<N> code.

Unlike most bulkstats counters (added one at a time via the Settings admin
panel), disc-reason-<N> is ~631 near-identical fields that all belong to a
single conceptual metric ("disconnects by reason") — seeding them through
the CRUD API one at a time isn't practical, so this bulk-inserts them
directly. Safe to re-run: skips (group, field_name) pairs that already exist.
"""

from __future__ import annotations

import asyncio

from sqlalchemy import select

from app.database import async_session_factory
from app.models.bulkstats import BulkstatsCounterCatalog
from app.services.bulkstats.disc_reasons import all_disc_reason_codes

METRIC_NAME = "bulkstats_disc_reason_count"


async def main() -> None:
    codes = all_disc_reason_codes()
    async with async_session_factory() as db:
        existing = (
            await db.execute(
                select(BulkstatsCounterCatalog.field_name).where(BulkstatsCounterCatalog.group == "system")
            )
        ).scalars().all()
        existing_fields = set(existing)

        created = 0
        for code in codes:
            field_name = f"disc-reason-{code}"
            if field_name in existing_fields:
                continue
            db.add(
                BulkstatsCounterCatalog(
                    group="system",
                    field_name=field_name,
                    metric_name=METRIC_NAME,
                    unit=None,
                    object_type="disc-reason",
                    enabled=True,
                )
            )
            created += 1
        await db.commit()
        print(f"created {created} catalog rows, skipped {len(codes) - created} already present")


if __name__ == "__main__":
    asyncio.run(main())
