from __future__ import annotations

import logging
from uuid import uuid4

from psycopg.types.json import Jsonb

from ..ports import (
    CandidateSummary,
    EmbeddingProfileMismatch,
    IdempotencyConflict,
    KnowledgeDetail,
    KnowledgeKind,
    KnowledgePreview,
    KnowledgeSummary,
    Page,
    PreviewExpired,
    PreviewMissing,
)
from .common import canonical_tag, database_errors, decode_cursor, digest, encode_cursor, vector_literal

SUMMARY_SQL = """SELECT k.*, COALESCE((SELECT jsonb_agg(t.name ORDER BY t.canonical_name)
 FROM knowledge_tags kt JOIN tags t ON t.id=kt.tag_id
 WHERE kt.knowledge_id=k.id AND kt.version=k.version), '[]'::jsonb) AS tags FROM knowledge k"""


def knowledge_detail(row) -> KnowledgeDetail:
    return KnowledgeDetail(
        **{
            key: row[key]
            for key in (
                "title",
                "kind",
                "summary",
                "tags",
                "version",
                "created_at",
                "updated_at",
                "status",
                "content",
            )
        },
        id=str(row["id"]),
    )


def preview_object(row) -> KnowledgePreview:
    return KnowledgePreview(
        preview_id=row["id"],
        **{key: row[key] for key in ("title", "kind", "content", "summary", "tags", "expires_at")},
    )


class KnowledgeMixin:
    @database_errors
    async def get_saved_preview(self, *, preview_id: str, idempotency_key: str) -> KnowledgeDetail | None:
        async with self.pool.connection() as connection:
            result = await (
                await connection.execute(
                    "SELECT * FROM ingestion_results WHERE idempotency_key=%s", (idempotency_key,)
                )
            ).fetchone()
            if result is None:
                return None
            if result["preview_id"] != preview_id:
                preview = await (
                    await connection.execute(
                        "SELECT input_digest FROM knowledge_previews WHERE id=%s", (preview_id,)
                    )
                ).fetchone()
                if not preview or preview["input_digest"] != result["input_digest"]:
                    raise IdempotencyConflict("Idempotency key was used with different input")
            row = await (
                await connection.execute(SUMMARY_SQL + " WHERE k.id=%s", (result["knowledge_id"],))
            ).fetchone()
            return knowledge_detail(row)

    @database_errors
    async def list_knowledge(
        self, *, q: str | None, kind: KnowledgeKind | None, tag: str | None, limit: int, cursor: str | None
    ) -> Page[KnowledgeSummary]:
        if not 1 <= limit <= 100:
            raise ValueError("Limit must be between 1 and 100")
        where, params = ["k.status='ready'"], []
        if q:
            where.append("(k.title ILIKE %s OR k.summary ILIKE %s)")
            params.extend(["%" + q + "%"] * 2)
        if kind:
            where.append("k.kind=%s")
            params.append(kind)
        if tag:
            where.append(
                "EXISTS (SELECT 1 FROM knowledge_tags kt JOIN tags t ON t.id=kt.tag_id WHERE kt.knowledge_id=k.id AND t.canonical_name=%s)"
            )
            params.append(canonical_tag(tag))
        position = decode_cursor(cursor, uuid_id=True)
        if position:
            where.append("(k.created_at,k.id)<(%s,%s::uuid)")
            params.extend(position)
        params.append(limit + 1)
        async with self.pool.connection() as connection:
            rows = await (
                await connection.execute(
                    SUMMARY_SQL
                    + " WHERE "
                    + " AND ".join(where)
                    + " ORDER BY k.created_at DESC,k.id DESC LIMIT %s",
                    params,
                )
            ).fetchall()
        entries = [knowledge_detail(row) for row in rows[:limit]]
        summaries = [
            KnowledgeSummary(**{key: getattr(entry, key) for key in KnowledgeSummary.__dataclass_fields__})
            for entry in entries
        ]
        return Page(
            items=summaries,
            next_cursor=encode_cursor(entries[-1].created_at, entries[-1].id) if len(rows) > limit else None,
        )

    @database_errors
    async def get_knowledge(self, knowledge_id: str) -> KnowledgeDetail | None:
        async with self.pool.connection() as connection:
            row = await (
                await connection.execute(
                    SUMMARY_SQL + " WHERE k.id::text=%s AND k.status='ready'", (knowledge_id,)
                )
            ).fetchone()
            return knowledge_detail(row) if row else None

    @database_errors
    async def create_preview(self, preview: KnowledgePreview) -> None:
        tags = sorted(
            {canonical_tag(tag): tag.strip() for tag in preview.tags if canonical_tag(tag)}.values(),
            key=canonical_tag,
        )
        if not tags:
            raise ValueError("Knowledge preview requires at least one tag")
        input_digest = digest([preview.title, preview.kind, preview.content, preview.summary, tags])
        async with self.pool.connection() as connection:
            await connection.execute(
                """INSERT INTO knowledge_previews(id,title,kind,content,summary,tags,input_digest,expires_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
                (
                    preview.preview_id,
                    preview.title,
                    preview.kind,
                    preview.content,
                    preview.summary,
                    Jsonb(tags),
                    input_digest,
                    preview.expires_at,
                ),
            )

    @database_errors
    async def get_preview(self, preview_id: str) -> KnowledgePreview:
        async with self.pool.connection() as connection:
            row = await (
                await connection.execute(
                    "SELECT *,expires_at<=now() AS expired FROM knowledge_previews WHERE id=%s", (preview_id,)
                )
            ).fetchone()
            if row is None:
                raise PreviewMissing("Preview was not found")
            if row["expired"]:
                raise PreviewExpired("Preview has expired; generate a new preview")
            return preview_object(row)

    async def _profile(self, connection, embedding_model, embedding_dimensions):
        row = await (
            await connection.execute("SELECT * FROM embedding_profiles WHERE active FOR SHARE")
        ).fetchone()
        if not row or row["model"] != embedding_model or row["dimensions"] != embedding_dimensions:
            raise EmbeddingProfileMismatch("Query and active embedding profile differ")
        return row["id"]

    @database_errors
    async def save_preview(
        self,
        *,
        preview_id: str,
        idempotency_key: str,
        tag_embeddings: dict[str, list[float]],
        embedding_model: str,
        embedding_dimensions: int,
    ) -> KnowledgeDetail:
        try:
            async with self.pool.connection() as connection:  # noqa: SIM117 - make transaction boundary explicit.
                async with connection.transaction():
                    # Serialize the same key even when no result row exists yet.
                    await connection.execute(
                        "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))", (idempotency_key,)
                    )
                    existing = await (
                        await connection.execute(
                            "SELECT * FROM ingestion_results WHERE idempotency_key=%s", (idempotency_key,)
                        )
                    ).fetchone()
                    if existing and existing["preview_id"] == preview_id:
                        row = await (
                            await connection.execute(
                                SUMMARY_SQL + " WHERE k.id=%s", (existing["knowledge_id"],)
                            )
                        ).fetchone()
                        return knowledge_detail(row)
                    preview = await (
                        await connection.execute(
                            "SELECT *,expires_at<=now() AS expired FROM knowledge_previews WHERE id=%s FOR UPDATE",
                            (preview_id,),
                        )
                    ).fetchone()
                    if preview is None:
                        raise PreviewMissing("Preview was not found")
                    if existing:
                        if existing["input_digest"] != preview["input_digest"]:
                            raise IdempotencyConflict("Idempotency key was used with different input")
                        row = await (
                            await connection.execute(
                                SUMMARY_SQL + " WHERE k.id=%s", (existing["knowledge_id"],)
                            )
                        ).fetchone()
                        return knowledge_detail(row)
                    if preview["expired"]:
                        raise PreviewExpired("Preview has expired; generate a new preview")
                    profile_id = await self._profile(connection, embedding_model, embedding_dimensions)
                    vectors = {
                        canonical_tag(key): vector_literal(value, embedding_dimensions)
                        for key, value in tag_embeddings.items()
                    }
                    required_tags = {canonical_tag(value) for value in preview["tags"]}
                    if set(vectors) != required_tags:
                        raise EmbeddingProfileMismatch("Embeddings must cover exactly the preview tags")
                    knowledge_id = uuid4()
                    await connection.execute(
                        """INSERT INTO knowledge(id,title,kind,content,summary,content_digest,status)
                        VALUES (%s,%s,%s,%s,%s,%s,'ready')""",
                        (
                            knowledge_id,
                            preview["title"],
                            preview["kind"],
                            preview["content"],
                            preview["summary"],
                            digest(preview["content"]),
                        ),
                    )
                    for tag in sorted(preview["tags"], key=canonical_tag):
                        canonical = canonical_tag(tag)
                        tag_row = await (
                            await connection.execute(
                                """INSERT INTO tags(id,name,canonical_name) VALUES (%s,%s,%s)
                            ON CONFLICT(canonical_name) DO UPDATE SET canonical_name=EXCLUDED.canonical_name RETURNING id""",
                                (uuid4(), tag, canonical),
                            )
                        ).fetchone()
                        await connection.execute(
                            """INSERT INTO tag_embeddings(tag_id,profile_id,embedding) VALUES(%s,%s,%s::vector)
                            ON CONFLICT(tag_id,profile_id) DO NOTHING""",
                            (tag_row["id"], profile_id, vectors[canonical]),
                        )
                        await connection.execute(
                            "INSERT INTO knowledge_tags(knowledge_id,version,tag_id) VALUES(%s,1,%s)",
                            (knowledge_id, tag_row["id"]),
                        )
                    await connection.execute(
                        "INSERT INTO ingestion_results(idempotency_key,preview_id,input_digest,knowledge_id) VALUES(%s,%s,%s,%s)",
                        (idempotency_key, preview_id, preview["input_digest"], knowledge_id),
                    )
                    row = await (
                        await connection.execute(SUMMARY_SQL + " WHERE k.id=%s", (knowledge_id,))
                    ).fetchone()
                    return knowledge_detail(row)
        except (PreviewMissing, PreviewExpired, IdempotencyConflict):
            raise
        except Exception:
            # Record a bounded metadata code in its own transaction after rollback.
            try:
                async with self.pool.connection() as connection:
                    await connection.execute(
                        "INSERT INTO ingestion_failures(id,preview_id,error_code) VALUES(%s,%s,%s)",
                        (uuid4(), preview_id, "INGESTION_FAILED"),
                    )
            except Exception:  # noqa: BLE001 - preserve original ingestion error.
                logging.getLogger(__name__).warning("ingestion_failure_metadata_write_failed")
            raise

    @database_errors
    async def retrieve_candidates(
        self,
        *,
        query_embeddings: dict[str, list[float]],
        embedding_model: str,
        embedding_dimensions: int,
        max_distance: float,
        per_tag_limit: int,
        candidate_limit: int,
    ) -> list[CandidateSummary]:
        if not 0 <= max_distance <= 2 or not 1 <= per_tag_limit <= 100 or not 1 <= candidate_limit <= 100:
            raise ValueError("Invalid retrieval limits")
        vectors = [vector_literal(vector, embedding_dimensions) for vector in query_embeddings.values()]
        if not vectors:
            return []
        async with self.pool.connection() as connection:  # noqa: SIM117 - pin profile within transaction.
            async with connection.transaction():
                profile_id = await self._profile(connection, embedding_model, embedding_dimensions)
                candidates = {}
                for vector in vectors:
                    rows = await (
                        await connection.execute(
                            """WITH nearest AS (
                        SELECT tag_id,embedding <=> %s::vector AS distance FROM tag_embeddings
                        WHERE profile_id=%s ORDER BY embedding <=> %s::vector,tag_id LIMIT %s)
                        SELECT k.id,k.title,k.kind,k.summary,k.version,min(n.distance) AS distance
                        FROM nearest n JOIN knowledge_tags kt ON kt.tag_id=n.tag_id
                        JOIN knowledge k ON k.id=kt.knowledge_id AND k.version=kt.version
                        WHERE n.distance<=%s AND k.status='ready'
                        GROUP BY k.id,k.title,k.kind,k.summary,k.version ORDER BY distance,k.id LIMIT %s""",
                            (vector, profile_id, vector, per_tag_limit, max_distance, candidate_limit),
                        )
                    ).fetchall()
                    for row in rows:
                        identifier = str(row["id"])
                        candidate = CandidateSummary(
                            id=identifier,
                            title=row["title"],
                            kind=row["kind"],
                            summary=row["summary"],
                            version=row["version"],
                            score=1 - float(row["distance"]),
                        )
                        if identifier not in candidates or candidate.score > candidates[identifier].score:
                            candidates[identifier] = candidate
                return sorted(candidates.values(), key=lambda item: (-item.score, item.id, item.version))[
                    :candidate_limit
                ]
