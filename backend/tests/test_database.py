"""Real PostgreSQL/pgvector tests. Set DATABASE_URL; there is no SQLite substitute."""

from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import psycopg
import pytest
import pytest_asyncio
from psycopg.conninfo import make_conninfo

from app.db import PostgresRepository
from app.ports import (
    ActivityEntry,
    EmbeddingProfileMismatch,
    IdempotencyConflict,
    KnowledgePreview,
    OutcomeEvent,
    OutcomeFeatures,
    PreviewExpired,
    RepositoryUnavailable,
    SourceRef,
)

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def repository():
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        pytest.skip("DATABASE_URL required for real PostgreSQL integration tests")
    schema = "test_" + uuid4().hex
    admin = await psycopg.AsyncConnection.connect(dsn, autocommit=True)
    await admin.execute("CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA public")
    await admin.execute(f"CREATE SCHEMA {schema}")
    repository = PostgresRepository(
        make_conninfo(dsn, options=f"-c search_path={schema},public"),
        embedding_model="test-embedding",
        embedding_dimensions=3,
    )
    try:
        await repository.open()
        yield repository
    finally:
        await repository.close()
        await admin.execute(f"DROP SCHEMA {schema} CASCADE")
        await admin.close()


def preview(*, tags=None, content="Intentional stored knowledge", expires=None):
    return KnowledgePreview(
        preview_id=str(uuid4()),
        title="Write tests",
        kind="skill",
        content=content,
        summary="Testing reference",
        tags=tags or ["Testing", "Python"],
        expires_at=expires or datetime.now(UTC) + timedelta(minutes=15),
    )


async def save(repository, value, key=None, vectors=None):
    await repository.create_preview(value)
    return await repository.save_preview(
        preview_id=value.preview_id,
        idempotency_key=key or str(uuid4()),
        tag_embeddings=vectors or {tag: [1, 0, 0] for tag in value.tags},
        embedding_model="test-embedding",
        embedding_dimensions=3,
    )


async def test_concurrent_idempotent_save_and_normalized_shared_tags(repository):
    first = preview(tags=["Python", "  PYTHON  ", "Testing"])
    await repository.create_preview(first)
    kwargs = {
        "preview_id": first.preview_id,
        "idempotency_key": "same-key",
        "tag_embeddings": {"Python": [1, 0, 0], "Testing": [0, 1, 0]},
        "embedding_model": "test-embedding",
        "embedding_dimensions": 3,
    }
    records = await asyncio.gather(*(repository.save_preview(**kwargs) for _ in range(4)))
    assert len({record.id for record in records}) == 1
    await save(repository, preview(tags=["python", "TESTING"]))
    async with repository.pool.connection() as connection:
        assert (await (await connection.execute("SELECT count(*) AS n FROM tags")).fetchone())["n"] == 2
        assert (await (await connection.execute("SELECT count(*) AS n FROM knowledge")).fetchone())["n"] == 2
        await connection.execute(
            "UPDATE knowledge_previews SET expires_at=now()-interval '1 second' WHERE id=%s",
            (first.preview_id,),
        )
    assert (
        await repository.get_saved_preview(preview_id=first.preview_id, idempotency_key="same-key")
    ).id == records[0].id
    assert (await repository.save_preview(**kwargs)).id == records[0].id
    different = preview(content="Different intentional content")
    await repository.create_preview(different)
    with pytest.raises(IdempotencyConflict):
        await repository.save_preview(**{**kwargs, "preview_id": different.preview_id})


async def test_database_failure_rolls_back_entire_ready_import(repository):
    value = preview(tags=["new-tag"])
    await repository.create_preview(value)
    async with repository.pool.connection() as connection:
        await connection.execute("""CREATE FUNCTION reject_link() RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN RAISE EXCEPTION 'injected link failure'; END $$""")
        await connection.execute(
            "CREATE TRIGGER reject_link BEFORE INSERT ON knowledge_tags FOR EACH ROW EXECUTE FUNCTION reject_link()"
        )
    with pytest.raises(RepositoryUnavailable):
        await repository.save_preview(
            preview_id=value.preview_id,
            idempotency_key="failed-key",
            tag_embeddings={"new-tag": [1, 0, 0]},
            embedding_model="test-embedding",
            embedding_dimensions=3,
        )
    async with repository.pool.connection() as connection:
        for table in ("knowledge", "tags", "tag_embeddings", "knowledge_tags", "ingestion_results"):
            assert (await (await connection.execute(f"SELECT count(*) AS n FROM {table}")).fetchone())[
                "n"
            ] == 0
        failures = await (await connection.execute("SELECT error_code FROM ingestion_failures")).fetchall()
        assert failures == [{"error_code": "INGESTION_FAILED"}]
        await connection.execute("DROP TRIGGER reject_link ON knowledge_tags")
    result = await repository.save_preview(
        preview_id=value.preview_id,
        idempotency_key="failed-key",
        tag_embeddings={"new-tag": [1, 0, 0]},
        embedding_model="test-embedding",
        embedding_dimensions=3,
    )
    assert result.status == "ready"


async def test_cosine_threshold_deduplication_caps_and_profile_mismatch(repository):
    match = await save(
        repository, preview(tags=["Python", "Tests"]), vectors={"Python": [1, 0, 0], "Tests": [0.99, 0.01, 0]}
    )
    await save(repository, preview(tags=["Unrelated"]), vectors={"Unrelated": [0, 0, 1]})
    kwargs = {
        "query_embeddings": {"p": [1, 0, 0], "t": [0.99, 0.01, 0]},
        "embedding_model": "test-embedding",
        "embedding_dimensions": 3,
        "max_distance": 0.1,
        "per_tag_limit": 5,
        "candidate_limit": 5,
    }
    results = await repository.retrieve_candidates(**kwargs)
    assert [item.id for item in results] == [match.id]
    assert results[0].score == pytest.approx(1)
    with pytest.raises(EmbeddingProfileMismatch):
        await repository.retrieve_candidates(**{**kwargs, "embedding_model": "wrong-model"})
    with pytest.raises(EmbeddingProfileMismatch):
        await repository.retrieve_candidates(**{**kwargs, "query_embeddings": {"bad": [1, 0]}})
    assert len(await repository.retrieve_candidates(**{**kwargs, "candidate_limit": 1})) == 1


async def test_expired_metadata_hidden_before_cleanup_and_purged(repository):
    now = datetime.now(UTC)
    timestamp = now - timedelta(days=31)
    expiry = timestamp + timedelta(days=30)
    entry = ActivityEntry(
        id="expired-api",
        request_id="old",
        timestamp=timestamp,
        operation="enhance",
        model=None,
        status="success",
        status_code=200,
        latency_ms=20,
        input_tokens=None,
        output_tokens=None,
        error_code=None,
        expires_at=expiry,
    )
    await repository.record_activity("api", entry)
    await repository.record_features(
        OutcomeFeatures(
            request_id="old",
            timestamp=timestamp,
            task_type="coding",
            missing_constraints_count=1,
            candidate_count=1,
            relevant_count=1,
            best_retrieval_score=0.9,
            enhancement_type="none",
            model_version="test-v1",
            expires_at=expiry,
        )
    )
    await repository.record_outcome(
        OutcomeEvent("old-event", "old", "observed", "helpful", timestamp, expiry)
    )
    await repository.record_sources(
        request_id="old", prompt_revision=1, sources=[SourceRef("k", "Title", "skill", 1)], expires_at=expiry
    )
    expired_preview = preview(expires=now - timedelta(seconds=1))
    await repository.create_preview(expired_preview)
    with pytest.raises(PreviewExpired):
        await repository.get_preview(expired_preview.preview_id)
    assert (await repository.list_activity(kind="api", status="all", limit=20, cursor=None)).items == []
    assert await repository.request_activity("old") is None
    assert await repository.get_sources("old") is None
    assert await repository.labeled_outcomes_count() == 0
    assert (await repository.export_outcomes()).items == []
    assert await repository.delete_expired() >= 5
    async with repository.pool.connection() as connection:
        assert (await (await connection.execute("SELECT count(*) AS n FROM outcome_events")).fetchone())[
            "n"
        ] == 0


async def test_settings_pagination_outcome_idempotency_and_safe_export(repository):
    now = datetime.now(UTC)
    expires = now + timedelta(days=30)
    assert await repository.get_models() is None
    await repository.set_models({"generation": "model-a", "summary": "model-b"})
    assert await repository.set_models({"generation": "model-c"}) == {
        "generation": "model-c",
        "summary": "model-b",
    }
    first = await save(repository, preview())
    await save(repository, preview(content="Second"))
    page = await repository.list_knowledge(q=None, kind=None, tag="PYTHON", limit=1, cursor=None)
    page2 = await repository.list_knowledge(q=None, kind=None, tag="python", limit=1, cursor=page.next_cursor)
    assert page.next_cursor and page.items[0].id != page2.items[0].id and page2.next_cursor is None
    event = OutcomeEvent("user-1", "req-1", "accepted", None, now, expires)
    assert await repository.record_outcome(event) == await repository.record_outcome(event)
    with pytest.raises(IdempotencyConflict):
        await repository.record_outcome(OutcomeEvent("user-1", "req-1", "declined", None, now, expires))
    assert await repository.labeled_outcomes_count() == 0
    await repository.record_features(
        OutcomeFeatures("req-1", now, "coding", 1, 2, 1, 0.9, "multiple_choice", "test-v1", expires)
    )
    await repository.record_outcome(OutcomeEvent("observed-1", "req-1", "observed", "helpful", now, expires))
    assert await repository.labeled_outcomes_count() == 1
    exported = (await repository.export_outcomes()).items
    assert len(exported) == 2
    first_export = await repository.export_outcomes(limit=1)
    second_export = await repository.export_outcomes(limit=1, cursor=first_export.next_cursor)
    assert (
        first_export.next_cursor and first_export.items[0]["event_id"] != second_export.items[0]["event_id"]
    )
    assert second_export.next_cursor is None
    assert all(
        "content" not in row
        and set(row["features"])
        == {
            "task_type",
            "missing_constraints_count",
            "candidate_count",
            "relevant_count",
            "best_retrieval_score",
            "enhancement_type",
            "model_version",
        }
        for row in exported
    )
    assert (await repository.get_knowledge(first.id)).content == "Intentional stored knowledge"


async def test_reindex_keeps_profiles_separate_and_checks_coverage(repository):
    from app.db.reindex import reindex

    await save(repository, preview(tags=["Python", "Tests"]))
    await reindex(repository, model="new-embedding-v2", vectors={"Python": [0, 1, 0]})
    with pytest.raises(EmbeddingProfileMismatch):
        await reindex(repository, model="new-embedding-v2", vectors={}, activate=True)
    async with repository.pool.connection() as connection:
        active = await (
            await connection.execute("SELECT model FROM embedding_profiles WHERE active")
        ).fetchone()
        assert active["model"] == "test-embedding"
    await reindex(
        repository, model="new-embedding-v2", vectors={"Python": [0, 1, 0], "Tests": [0, 1, 0]}, activate=True
    )
    kwargs = {
        "query_embeddings": {"test": [0, 1, 0]},
        "embedding_model": "new-embedding-v2",
        "embedding_dimensions": 3,
        "max_distance": 0.1,
        "per_tag_limit": 5,
        "candidate_limit": 5,
    }
    assert len(await repository.retrieve_candidates(**kwargs)) == 1
    with pytest.raises(EmbeddingProfileMismatch):
        await repository.retrieve_candidates(**{**kwargs, "embedding_model": "test-embedding"})


async def test_pool_logging_redacts_connection_secrets(caplog):
    import logging

    repository = PostgresRepository("postgresql://localhost/unused", auto_migrate=False)
    logger = logging.getLogger("psycopg.pool")
    with caplog.at_level(logging.WARNING, logger="psycopg.pool"):
        logger.warning("connection failed: %s", "postgresql://user:SECRET_SENTINEL@host/db")
    assert "SECRET_SENTINEL" not in caplog.text
    assert "postgres_pool_event" in caplog.text
    await repository.close()
