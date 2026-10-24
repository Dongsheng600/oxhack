"""Local browser QA fixture. Never import this module from production code.

The API routes and PostgreSQL writes are real; only Gemini is replaced with a
deterministic provider. Tables live in a dedicated ``prompt_enhance_qa`` schema.
"""

from __future__ import annotations

import asyncio
from dataclasses import replace
from uuid import uuid4

import psycopg
from psycopg.conninfo import make_conninfo

from app.config import Config
from app.db import PostgresRepository
from app.errors import ServiceError
from app.main import create_app
from app.provider import (
    AIResult,
    Extraction,
    GeneratedEdit,
    GeneratedOption,
    Generation,
    Relevance,
    SourceSummary,
)
from app.schemas import PreviewRequest
from app.service import EnhanceService
from app.utf16 import utf16_length

SCHEMA = "prompt_enhance_qa"


class QAProvider:
    async def close(self) -> None:
        pass

    async def extract(self, *, prompt: str, model: str) -> AIResult[Extraction]:
        if "[[error]]" in prompt:
            raise ServiceError(503, "gemini_unavailable", "Gemini is unavailable. Retry the request.", True)
        return AIResult(Extraction(tags=["ui testing"], task_type="coding", missing_constraints=["output format"]))

    async def relevance(self, *, prompt: str, summary: str, model: str) -> AIResult[Relevance]:
        return AIResult(Relevance(include="ui" in summary.lower()))

    async def generate(
        self, *, prompt: str, cursor_position: int, knowledge: list[str], model: str,
    ) -> AIResult[Generation]:
        if "[[none]]" in prompt:
            return AIResult(Generation(type="none"))
        if "[[choice]]" in prompt or cursor_position != utf16_length(prompt):
            position = utf16_length(prompt)
            return AIResult(Generation(
                type="multiple_choice", question="Which level of detail should the response use?",
                options=[
                    GeneratedOption(id="brief", label="Brief", edits=[GeneratedEdit(
                        start=position, end=position, text="\nKeep the answer brief.",
                    )]),
                    GeneratedOption(id="detailed", label="Detailed", edits=[GeneratedEdit(
                        start=position, end=position, text="\nInclude rationale and examples.",
                    )]),
                ],
            ))
        return AIResult(Generation(
            type="autocomplete", insert_at=utf16_length(prompt),
            text=" with clear acceptance criteria.",
        ))

    async def summarize(self, *, title: str, kind: str, content: str, model: str) -> AIResult[SourceSummary]:
        if "[[error]]" in content:
            raise ServiceError(503, "gemini_unavailable", "Gemini is unavailable. Retry the request.", True)
        return AIResult(SourceSummary(summary=f"UI testing reference for {title}.", tags=["ui testing"]))

    async def embed(self, *, text: str, task_type: str, model: str, dimensions: int) -> AIResult[list[float]]:
        return AIResult([1.0] + [0.0] * (dimensions - 1))

    async def embed_many(self, *, texts: list[str], task_type: str, model: str, dimensions: int) -> AIResult[list[list[float]]]:
        return AIResult([[1.0] + [0.0] * (dimensions - 1) for _ in texts])


def qa_config() -> tuple[Config, PostgresRepository]:
    base = Config.from_env()
    if not base.database_url:
        raise RuntimeError("DATABASE_URL is required for the QA server")
    with psycopg.connect(base.database_url.replace("postgresql+psycopg://", "postgresql://", 1)) as connection:
        connection.execute(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}")
    qa_dsn = make_conninfo(
        base.database_url.replace("postgresql+psycopg://", "postgresql://", 1),
        options=f"-c search_path={SCHEMA},public",
    )
    config = replace(base, database_url=qa_dsn, gemini_api_key="qa_fixture",
                     snowflake_account=None, snowflake_user=None, snowflake_password=None,
                     snowflake_warehouse=None, snowflake_database=None, snowflake_model_version=None)
    repo = PostgresRepository(qa_dsn, embedding_model=config.embedding_model,
                              embedding_dimensions=config.embedding_dimensions)
    return config, repo


config, repository = qa_config()
app = create_app(config=config, repository=repository, provider=QAProvider())


async def seed() -> None:
    await repository.open()
    try:
        service = EnhanceService(repository, QAProvider(), config)
        fixtures = [
            ("Interface testing checklist", "skill", "Check keyboard access, visible focus, responsive layout, error recovery, and concrete acceptance criteria."),
            ("Prompt refinement example", "prompt", "Ask a clear question when output detail is missing. Never assume the user's preferred format."),
            ("Review flow graph", "graph", "Draft → suggest → review diff → confirm or decline. Preserve the original draft until confirmation."),
        ]
        for title, kind, content in fixtures:
            existing = await repository.list_knowledge(q=title, kind=None, tag=None, cursor=None, limit=1)
            if existing.items:
                continue
            preview = await service.preview(PreviewRequest(title=title, kind=kind, content=content), str(uuid4()))
            await service.save(preview_id=preview.preview_id, idempotency_key=f"qa_{kind}_{title.replace(' ', '_')}", request_id=str(uuid4()))
    finally:
        await repository.close()


if __name__ == "__main__":
    asyncio.run(seed())
