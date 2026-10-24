from __future__ import annotations

import math
import re
from collections.abc import Sequence
from dataclasses import asdict
from datetime import datetime, timedelta
from typing import Literal
from uuid import uuid4

from psycopg.types.json import Jsonb

from ..ports import (
    ActivityEntry,
    ActivityKind,
    IdempotencyConflict,
    OutcomeEvent,
    OutcomeFeatures,
    Page,
    SourceRef,
)
from .common import database_errors, decode_cursor, digest, encode_cursor

ACTIVITY_COLUMNS = tuple(ActivityEntry.__dataclass_fields__)


def activity_object(row) -> ActivityEntry:
    return ActivityEntry(**{key: row[key] for key in ACTIVITY_COLUMNS})


def safe_expiry(timestamp: datetime, expires_at: datetime) -> datetime:
    if timestamp.tzinfo is None or expires_at.tzinfo is None:
        raise ValueError("Timestamps must include a timezone")
    return min(expires_at, timestamp + timedelta(days=30))


class TelemetryMixin:
    @database_errors
    async def record_sources(
        self, *, request_id: str, prompt_revision: int, sources: Sequence[SourceRef], expires_at: datetime
    ) -> None:
        async with self.pool.connection() as connection:
            await connection.execute(
                """INSERT INTO request_sources(request_id,prompt_revision,sources,expires_at)
                VALUES(%s,%s,%s,LEAST(%s,now()+interval '30 days'))
                ON CONFLICT(request_id) DO UPDATE SET prompt_revision=EXCLUDED.prompt_revision,sources=EXCLUDED.sources,
                expires_at=LEAST(request_sources.expires_at,EXCLUDED.expires_at)""",
                (request_id, prompt_revision, Jsonb([asdict(source) for source in sources]), expires_at),
            )

    @database_errors
    async def get_sources(self, request_id: str) -> tuple[int, list[SourceRef]] | None:
        async with self.pool.connection() as connection:
            row = await (
                await connection.execute(
                    "SELECT * FROM request_sources WHERE request_id=%s AND expires_at>now()", (request_id,)
                )
            ).fetchone()
            return (
                (row["prompt_revision"], [SourceRef(**source) for source in row["sources"]]) if row else None
            )

    @database_errors
    async def record_activity(self, kind: ActivityKind, entry: ActivityEntry) -> None:
        values = asdict(entry)
        values["expires_at"] = safe_expiry(entry.timestamp, entry.expires_at)
        async with self.pool.connection() as connection:
            await connection.execute(
                """INSERT INTO activity_logs(id,request_id,timestamp,operation,model,status,status_code,
                latency_ms,input_tokens,output_tokens,error_code,expires_at,kind)
                VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(id) DO NOTHING""",
                tuple(values[key] for key in ACTIVITY_COLUMNS) + (kind,),
            )

    @database_errors
    async def list_activity(
        self,
        *,
        kind: ActivityKind,
        status: Literal["all", "success", "error"],
        limit: int,
        cursor: str | None,
    ) -> Page[ActivityEntry]:
        if not 1 <= limit <= 100:
            raise ValueError("Limit must be between 1 and 100")
        where, params = ["kind=%s", "expires_at>now()"], [kind]
        if status != "all":
            where.append("status=%s")
            params.append(status)
        position = decode_cursor(cursor)
        if position:
            where.append("(timestamp,id)<(%s,%s)")
            params.extend(position)
        params.append(limit + 1)
        async with self.pool.connection() as connection:
            rows = await (
                await connection.execute(
                    "SELECT * FROM activity_logs WHERE "
                    + " AND ".join(where)
                    + " ORDER BY timestamp DESC,id DESC LIMIT %s",
                    params,
                )
            ).fetchall()
            items = [activity_object(row) for row in rows[:limit]]
            return Page(
                items=items,
                next_cursor=encode_cursor(items[-1].timestamp, items[-1].id) if len(rows) > limit else None,
            )

    @database_errors
    async def request_activity(
        self, request_id: str
    ) -> tuple[list[ActivityEntry], list[ActivityEntry], list[SourceRef], datetime] | None:
        async with self.pool.connection() as connection:
            rows = await (
                await connection.execute(
                    "SELECT * FROM activity_logs WHERE request_id=%s AND expires_at>now() ORDER BY timestamp,id",
                    (request_id,),
                )
            ).fetchall()
            source = await (
                await connection.execute(
                    "SELECT * FROM request_sources WHERE request_id=%s AND expires_at>now()", (request_id,)
                )
            ).fetchone()
            if not rows and not source:
                return None
            api = [activity_object(row) for row in rows if row["kind"] == "api"]
            ai = [activity_object(row) for row in rows if row["kind"] == "ai"]
            sources = [SourceRef(**item) for item in source["sources"]] if source else []
            expiries = [row["expires_at"] for row in rows] + ([source["expires_at"]] if source else [])
            return api, ai, sources, min(expiries)

    @database_errors
    async def record_outcome(self, event: OutcomeEvent) -> str:
        input_digest = digest([event.request_id, event.event_type, event.observed_result])
        async with self.pool.connection() as connection:
            row = await (
                await connection.execute(
                    """INSERT INTO outcome_events(id,event_id,request_id,event_type,observed_result,timestamp,expires_at,input_digest)
                VALUES(%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(event_id) DO UPDATE SET event_id=EXCLUDED.event_id
                RETURNING id,input_digest""",
                    (
                        uuid4(),
                        event.event_id,
                        event.request_id,
                        event.event_type,
                        event.observed_result,
                        event.timestamp,
                        safe_expiry(event.timestamp, event.expires_at),
                        input_digest,
                    ),
                )
            ).fetchone()
            if row["input_digest"] != input_digest:
                raise IdempotencyConflict("Event ID was used with different input")
            return str(row["id"])

    @database_errors
    async def record_features(self, features: OutcomeFeatures) -> None:
        approved = {
            key: getattr(features, key)
            for key in (
                "task_type",
                "missing_constraints_count",
                "candidate_count",
                "relevant_count",
                "best_retrieval_score",
                "enhancement_type",
                "model_version",
            )
        }
        if approved["task_type"] not in {"coding", "writing", "analysis", "research", "planning", "other"}:
            raise ValueError("Unknown derived task category")
        if approved["enhancement_type"] not in {"autocomplete", "multiple_choice", "none"}:
            raise ValueError("Unknown suggestion category")
        if not re.fullmatch(r"[A-Za-z0-9_.:/+-]{1,160}", approved["model_version"]):
            raise ValueError("Invalid derived model version")
        for key in ("missing_constraints_count", "candidate_count", "relevant_count"):
            if type(approved[key]) is not int or not 0 <= approved[key] <= 100000:
                raise ValueError("Invalid derived count")
        score = approved["best_retrieval_score"]
        if score is not None and (
            not isinstance(score, (int, float)) or not math.isfinite(score) or not -1 <= score <= 1
        ):
            raise ValueError("Invalid derived retrieval score")
        async with self.pool.connection() as connection:
            await connection.execute(
                """INSERT INTO request_features(request_id,features,created_at,expires_at)
                VALUES(%s,%s,%s,%s) ON CONFLICT(request_id) DO NOTHING""",
                (
                    features.request_id,
                    Jsonb(approved),
                    features.timestamp,
                    safe_expiry(features.timestamp, features.expires_at),
                ),
            )

    @database_errors
    async def export_outcomes(
        self, *, limit: int = 500, cursor: str | None = None
    ) -> Page[dict[str, object]]:
        if not 1 <= limit <= 5000:
            raise ValueError("Invalid export limit")
        position = decode_cursor(cursor, uuid_id=True)
        where = " AND (o.timestamp,o.id)>(%s,%s::uuid)" if position else ""
        parameters = (*position, limit + 1) if position else (limit + 1,)
        async with self.pool.connection() as connection:
            rows = await (
                await connection.execute(
                    """SELECT o.id::text AS event_id,o.request_id,o.event_type,o.observed_result,
                o.timestamp,LEAST(o.expires_at,f.expires_at) AS expires_at,f.feature_schema,f.features
                FROM outcome_events o JOIN request_features f ON f.request_id=o.request_id
                WHERE o.expires_at>now() AND f.expires_at>now()"""
                    + where
                    + " ORDER BY o.timestamp,o.id LIMIT %s",
                    parameters,
                )
            ).fetchall()
            items = [dict(row) for row in rows[:limit]]
            return Page(
                items=items,
                next_cursor=encode_cursor(items[-1]["timestamp"], items[-1]["event_id"])
                if len(rows) > limit
                else None,
            )

    @database_errors
    async def labeled_outcomes_count(self) -> int:
        async with self.pool.connection() as connection:
            row = await (
                await connection.execute("""SELECT count(DISTINCT request_id) AS count FROM outcome_events
                WHERE event_type='observed' AND observed_result IN ('helpful','unhelpful') AND expires_at>now()""")
            ).fetchone()
            return row["count"]

    @database_errors
    async def delete_expired(self, *, batch_size: int = 500) -> int:
        if not 1 <= batch_size <= 10000:
            raise ValueError("Invalid cleanup batch size")
        count = 0
        async with self.pool.connection() as connection:
            for table in (
                "activity_logs",
                "outcome_events",
                "request_sources",
                "request_features",
                "knowledge_previews",
                "ingestion_failures",
            ):
                # Identifiers come only from this fixed allowlist. Skip locked rows makes
                # periodic cleanup safe across multiple API replicas.
                cursor = await connection.execute(
                    f"""DELETE FROM {table} WHERE ctid IN
                    (SELECT ctid FROM {table} WHERE expires_at<=now() LIMIT %s FOR UPDATE SKIP LOCKED)""",
                    (batch_size,),
                )
                count += cursor.rowcount
        return count
