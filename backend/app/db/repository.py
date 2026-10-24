"""Production async PostgreSQL/pgvector repository."""

from __future__ import annotations

import logging

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from psycopg_pool import AsyncConnectionPool

from .common import MetadataOnlyPoolFilter, database_errors
from .knowledge import KnowledgeMixin
from .migrations import migrate
from .telemetry import TelemetryMixin


class PostgresRepository(KnowledgeMixin, TelemetryMixin):
    def __init__(
        self,
        dsn: str,
        *,
        embedding_model: str = "gemini-embedding-001",
        embedding_dimensions: int = 768,
        auto_migrate: bool = True,
        min_size: int = 1,
        max_size: int = 10,
    ) -> None:
        pool_logger = logging.getLogger("psycopg.pool")
        if not any(isinstance(item, MetadataOnlyPoolFilter) for item in pool_logger.filters):
            pool_logger.addFilter(MetadataOnlyPoolFilter())
        self.embedding_model = embedding_model
        self.embedding_dimensions = embedding_dimensions
        self.auto_migrate = auto_migrate
        self.pool = AsyncConnectionPool(
            dsn.replace("postgresql+psycopg://", "postgresql://"),
            min_size=min_size,
            max_size=max_size,
            open=False,
            timeout=10,
            kwargs={"row_factory": dict_row, "connect_timeout": 10},
            # Avoid logging exception messages containing connection credentials.
            reconnect_failed=self._reconnect_failed,
        )

    @staticmethod
    async def _reconnect_failed(pool):
        return None

    @database_errors
    async def open(self) -> None:
        await self.pool.open(wait=True, timeout=15)
        if self.auto_migrate:
            async with self.pool.connection() as connection:
                await migrate(
                    connection,
                    embedding_model=self.embedding_model,
                    embedding_dimensions=self.embedding_dimensions,
                )

    async def close(self) -> None:
        await self.pool.close()

    async def health(self) -> bool:
        try:
            async with self.pool.connection(timeout=2) as connection:
                await connection.execute("SELECT 1")
            return True
        except Exception:  # noqa: BLE001 - readiness must fail closed for any pool failure.
            return False

    @database_errors
    async def get_models(self) -> dict[str, str] | None:
        async with self.pool.connection() as connection:
            row = await (
                await connection.execute("SELECT models FROM model_settings WHERE singleton")
            ).fetchone()
            return row["models"] if row else None

    @database_errors
    async def set_models(self, updates: dict[str, str]) -> dict[str, str]:
        async with self.pool.connection() as connection:
            row = await (
                await connection.execute(
                    """INSERT INTO model_settings(singleton,models) VALUES(true,%s)
                ON CONFLICT(singleton) DO UPDATE SET models=model_settings.models || EXCLUDED.models,
                revision=model_settings.revision+1,updated_at=now() RETURNING models""",
                    (Jsonb(updates),),
                )
            ).fetchone()
            return row["models"]
