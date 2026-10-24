from __future__ import annotations

import asyncio
import unicodedata
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from time import perf_counter
from typing import TypeVar
from uuid import uuid4

from pydantic import TypeAdapter, ValidationError

from .config import DEFAULT_MODELS, Config
from .errors import ServiceError, malformed
from .ports import (
    ActivityEntry,
    CandidateSummary,
    KnowledgeDetail,
    KnowledgePreview,
    OutcomeFeatures,
    Repository,
    SourceRef,
)
from .provider import AIProvider, AIResult, Generation
from .schemas import EnhanceRequest, EnhanceResponse, PreviewRequest, validate_enhancement

T = TypeVar("T")
RESPONSE_ADAPTER = TypeAdapter(EnhanceResponse)
RETENTION = timedelta(days=30)


def utc_now() -> datetime:
    return datetime.now(UTC)


def normalize_tags(tags: list[str]) -> list[str]:
    normalized: list[str] = []
    for tag in tags:
        clean = " ".join(unicodedata.normalize("NFKC", tag).casefold().split())
        if clean and len(clean) <= 80 and clean not in normalized:
            normalized.append(clean)
    return normalized[:8]


class EnhanceService:
    def __init__(self, repo: Repository, provider: AIProvider, config: Config) -> None:
        self.repo = repo
        self.provider = provider
        self.config = config

    async def models(self) -> dict[str, str]:
        stored = await self.repo.get_models()
        return {**DEFAULT_MODELS, **(stored or {})}

    async def _ai(
        self, *, request_id: str, operation: str, model: str,
        call: Callable[[], Awaitable[AIResult[T]]],
    ) -> T:
        started = perf_counter()
        timestamp = utc_now()
        status = "success"
        code: str | None = None
        usage: AIResult[T] | None = None
        try:
            usage = await call()
            return usage.value
        except ServiceError as exc:
            status, code = "error", exc.code
            raise
        except Exception:  # noqa: BLE001 - provider failures must be sanitized.
            status, code = "error", "provider_unavailable"
            raise ServiceError(503, code, "The AI provider is unavailable. Retry the request.", True) from None
        finally:
            await self.repo.record_activity("ai", ActivityEntry(
                id=str(uuid4()), request_id=request_id, timestamp=timestamp,
                operation=operation, model=model, status=status, status_code=None,
                latency_ms=round((perf_counter() - started) * 1000),
                input_tokens=usage.input_tokens if usage else None,
                output_tokens=usage.output_tokens if usage else None,
                error_code=code, expires_at=timestamp + RETENTION,
            ))

    async def enhance(self, request: EnhanceRequest) -> EnhanceResponse:
        async with asyncio.timeout(self.config.deadline_seconds):
            return await self._enhance(request)

    async def _enhance(self, request: EnhanceRequest) -> EnhanceResponse:
        models = await self.models()
        extraction = await self._ai(
            request_id=request.request_id, operation="extraction", model=models["extraction"],
            call=lambda: self.provider.extract(prompt=request.prompt, model=models["extraction"]),
        )
        tags = normalize_tags(extraction.tags)
        candidates: list[CandidateSummary] = []
        if tags:
            vectors = await self._ai(
                request_id=request.request_id, operation="embedding_query", model=self.config.embedding_model,
                call=lambda: self.provider.embed_many(
                    texts=tags, task_type="RETRIEVAL_QUERY", model=self.config.embedding_model,
                    dimensions=self.config.embedding_dimensions,
                ),
            )
            if len(vectors) != len(tags):
                raise malformed("embedding")
            embeddings = dict(zip(tags, vectors, strict=True))
            candidates = await self.repo.retrieve_candidates(
                query_embeddings=embeddings, embedding_model=self.config.embedding_model,
                embedding_dimensions=self.config.embedding_dimensions,
                max_distance=self.config.max_distance, per_tag_limit=self.config.per_tag_limit,
                candidate_limit=self.config.candidate_limit,
            )

        semaphore = asyncio.Semaphore(self.config.relevance_concurrency)

        async def judge(candidate: CandidateSummary) -> bool:
            async with semaphore:
                result = await self._ai(
                    request_id=request.request_id, operation="relevance", model=models["relevance"],
                    call=lambda: self.provider.relevance(
                        prompt=request.prompt, summary=candidate.summary, model=models["relevance"],
                    ),
                )
                return result.include

        judgments = await asyncio.gather(*(judge(candidate) for candidate in candidates))
        included = [candidate for candidate, use in zip(candidates, judgments) if use]
        details: list[KnowledgeDetail] = []
        reference_chars = 0
        for candidate in included[: self.config.included_source_limit]:
            detail = await self.repo.get_knowledge(candidate.id)
            if detail is None or detail.version != candidate.version or detail.status != "ready":
                raise ServiceError(503, "knowledge_changed", "A retrieved source changed during enhancement. Retry the request.", True)
            if reference_chars + len(detail.content) > self.config.reference_context_chars:
                continue
            details.append(detail)
            reference_chars += len(detail.content)

        generated = await self._ai(
            request_id=request.request_id, operation="generation", model=models["generation"],
            call=lambda: self.provider.generate(
                prompt=request.prompt, cursor_position=request.cursor_position,
                knowledge=[detail.content for detail in details], model=models["generation"],
            ),
        )
        response = self._validate_generation(generated, request)
        now = utc_now()
        sources = [SourceRef(detail.id, detail.title, detail.kind, detail.version) for detail in details]
        await self.repo.record_sources(
            request_id=request.request_id, prompt_revision=request.prompt_revision,
            sources=sources, expires_at=now + RETENTION,
        )
        await self.repo.record_features(OutcomeFeatures(
            request_id=request.request_id, timestamp=now,
            task_type=extraction.task_type,
            missing_constraints_count=len(extraction.missing_constraints),
            candidate_count=len(candidates), relevant_count=len(included),
            best_retrieval_score=max((candidate.score for candidate in candidates), default=None),
            enhancement_type=response.type, model_version=models["generation"],
            expires_at=now + RETENTION,
        ))
        return response

    @staticmethod
    def _validate_generation(generated: Generation, request: EnhanceRequest) -> EnhanceResponse:
        raw = generated.model_dump(exclude_none=True)
        raw.update(schema_version=1, request_id=request.request_id, prompt_revision=request.prompt_revision)
        try:
            response = RESPONSE_ADAPTER.validate_python(raw)
            validate_enhancement(response, request.prompt)
            return response
        except (ValidationError, ValueError):
            raise malformed("generation") from None

    async def preview(self, request: PreviewRequest, request_id: str) -> KnowledgePreview:
        models = await self.models()
        result = await self._ai(
            request_id=request_id, operation="summary", model=models["summary"],
            call=lambda: self.provider.summarize(
                title=request.title, kind=request.kind, content=request.content,
                model=models["summary"],
            ),
        )
        tags = normalize_tags(result.tags)
        if not tags:
            raise malformed("summary")
        preview = KnowledgePreview(
            preview_id=str(uuid4()), title=request.title, kind=request.kind,
            content=request.content, summary=result.summary, tags=tags,
            expires_at=utc_now() + timedelta(seconds=self.config.preview_ttl_seconds),
        )
        await self.repo.create_preview(preview)
        return preview

    async def save(self, *, preview_id: str, idempotency_key: str, request_id: str) -> KnowledgeDetail:
        existing = await self.repo.get_saved_preview(preview_id=preview_id, idempotency_key=idempotency_key)
        if existing is not None:
            return existing
        preview = await self.repo.get_preview(preview_id)
        embeddings = await self._ai(
            request_id=request_id, operation="embedding_document", model=self.config.embedding_model,
            call=lambda: self.provider.embed_many(
                texts=preview.tags, task_type="RETRIEVAL_DOCUMENT", model=self.config.embedding_model,
                dimensions=self.config.embedding_dimensions,
            ),
        )
        if len(embeddings) != len(preview.tags):
            raise malformed("embedding")
        vectors = dict(zip(preview.tags, embeddings, strict=True))
        return await self.repo.save_preview(
            preview_id=preview_id, idempotency_key=idempotency_key,
            tag_embeddings=vectors, embedding_model=self.config.embedding_model,
            embedding_dimensions=self.config.embedding_dimensions,
        )
