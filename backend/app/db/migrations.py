"""Versioned PostgreSQL migrations; no SQLite or in-memory production fallback."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from ..ports import EmbeddingProfileMismatch


async def migrate(connection, *, embedding_model: str, embedding_dimensions: int) -> None:
    if not 1 <= embedding_dimensions <= 2000:
        raise ValueError("Embedding dimensions must be between 1 and 2000 for the HNSW index")
    async with connection.transaction():
        await connection.execute("SELECT pg_advisory_xact_lock(734276182)")
        await connection.execute("""CREATE TABLE IF NOT EXISTS schema_migrations (
            version text PRIMARY KEY, dimensions integer NOT NULL, applied_at timestamptz NOT NULL DEFAULT now())""")
        rows = await (
            await connection.execute("SELECT version, dimensions FROM schema_migrations")
        ).fetchall()
        applied = {row["version"]: row["dimensions"] for row in rows}
        if applied and any(value != embedding_dimensions for value in applied.values()):
            raise ValueError("Database vector dimensions differ; use controlled reindex migration")
        migration_root = Path(__file__).resolve().parents[3] / "database" / "migrations"
        # Docker packages migrations under /app/database, adjacent to backend/app.
        if not migration_root.exists():
            migration_root = Path(__file__).resolve().parents[2] / "database" / "migrations"
        if not migration_root.exists():
            migration_root = Path(__file__).resolve().parent / "sql"
        for path in sorted(migration_root.glob("*.sql")):
            if path.stem not in applied:
                await connection.execute(
                    path.read_text().replace("__DIMENSIONS__", str(embedding_dimensions))
                )
                await connection.execute(
                    "INSERT INTO schema_migrations(version,dimensions) VALUES (%s,%s)",
                    (path.stem, embedding_dimensions),
                )
        if not list(migration_root.glob("*.sql")):
            raise RuntimeError("Database migrations are missing from the application package")
        active = await (
            await connection.execute("SELECT model,dimensions FROM embedding_profiles WHERE active")
        ).fetchone()
        if active and (active["model"] != embedding_model or active["dimensions"] != embedding_dimensions):
            raise EmbeddingProfileMismatch(
                "Configured embedding model differs from the active database profile; reindex before changing configuration"
            )
        if not active:
            await connection.execute(
                """INSERT INTO embedding_profiles(id,model,dimensions,metric,active)
                VALUES (%s,%s,%s,'cosine',true) ON CONFLICT (model,dimensions,normalization_version) DO UPDATE SET active=true""",
                (uuid4(), embedding_model, embedding_dimensions),
            )
