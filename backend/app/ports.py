"""Typed boundaries between API/orchestration and persistence/provider adapters.

Repository implementations may return their own immutable objects as long as they
conform to these shapes. Times are timezone-aware UTC datetimes.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Protocol

KnowledgeKind = Literal["skill", "prompt", "graph"]
ActivityKind = Literal["api", "ai"]
OutcomeType = Literal["displayed", "accepted", "declined", "stale", "failed", "observed"]
ObservedResult = Literal["helpful", "unhelpful", "unknown"]


class RepositoryUnavailable(Exception):
    pass


class PreviewMissing(Exception):
    pass


class PreviewExpired(Exception):
    pass


class IdempotencyConflict(Exception):
    pass


class EmbeddingProfileMismatch(Exception):
    pass


@dataclass(frozen=True)
class KnowledgeSummary:
    id: str
    title: str
    kind: KnowledgeKind
    summary: str
    tags: list[str]
    version: int
    created_at: datetime
    updated_at: datetime
    status: str


@dataclass(frozen=True)
class KnowledgeDetail(KnowledgeSummary):
    content: str


@dataclass(frozen=True)
class KnowledgePreview:
    preview_id: str
    title: str
    kind: KnowledgeKind
    content: str
    summary: str
    tags: list[str]
    expires_at: datetime


@dataclass(frozen=True)
class CandidateSummary:
    id: str
    title: str
    kind: KnowledgeKind
    summary: str
    version: int
    score: float


@dataclass(frozen=True)
class SourceRef:
    id: str
    title: str
    kind: KnowledgeKind
    version: int


@dataclass(frozen=True)
class ActivityEntry:
    id: str
    request_id: str
    timestamp: datetime
    operation: str
    model: str | None
    status: str
    status_code: int | None
    latency_ms: int
    input_tokens: int | None
    output_tokens: int | None
    error_code: str | None
    expires_at: datetime


@dataclass(frozen=True)
class OutcomeEvent:
    event_id: str
    request_id: str
    event_type: OutcomeType
    observed_result: ObservedResult | None
    timestamp: datetime
    expires_at: datetime


@dataclass(frozen=True)
class OutcomeFeatures:
    request_id: str
    timestamp: datetime
    task_type: str
    missing_constraints_count: int
    candidate_count: int
    relevant_count: int
    best_retrieval_score: float | None
    enhancement_type: Literal["autocomplete", "multiple_choice", "none"]
    model_version: str
    expires_at: datetime


@dataclass(frozen=True)
class Page[T]:
    items: list[T]
    next_cursor: str | None


class Repository(Protocol):
    async def open(self) -> None: ...
    async def close(self) -> None: ...
    async def health(self) -> bool: ...

    async def get_models(self) -> dict[str, str] | None: ...
    async def set_models(self, updates: dict[str, str]) -> dict[str, str]: ...

    async def list_knowledge(
        self, *, q: str | None, kind: KnowledgeKind | None,
        tag: str | None, limit: int, cursor: str | None,
    ) -> Page[KnowledgeSummary]: ...
    async def get_knowledge(self, knowledge_id: str) -> KnowledgeDetail | None: ...
    async def create_preview(self, preview: KnowledgePreview) -> None: ...
    async def get_preview(self, preview_id: str) -> KnowledgePreview: ...
    async def get_saved_preview(self, *, preview_id: str, idempotency_key: str) -> KnowledgeDetail | None: ...
    async def save_preview(
        self, *, preview_id: str, idempotency_key: str,
        tag_embeddings: dict[str, list[float]], embedding_model: str,
        embedding_dimensions: int,
    ) -> KnowledgeDetail: ...

    async def retrieve_candidates(
        self, *, query_embeddings: dict[str, list[float]],
        embedding_model: str, embedding_dimensions: int,
        max_distance: float, per_tag_limit: int, candidate_limit: int,
    ) -> list[CandidateSummary]: ...

    async def record_sources(
        self, *, request_id: str, prompt_revision: int,
        sources: Sequence[SourceRef], expires_at: datetime,
    ) -> None: ...
    async def get_sources(self, request_id: str) -> tuple[int, list[SourceRef]] | None: ...

    async def record_activity(self, kind: ActivityKind, entry: ActivityEntry) -> None: ...
    async def list_activity(
        self, *, kind: ActivityKind, status: Literal["all", "success", "error"],
        limit: int, cursor: str | None,
    ) -> Page[ActivityEntry]: ...
    async def request_activity(
        self, request_id: str,
    ) -> tuple[list[ActivityEntry], list[ActivityEntry], list[SourceRef], datetime] | None: ...

    async def record_outcome(self, event: OutcomeEvent) -> str: ...
    async def record_features(self, features: OutcomeFeatures) -> None: ...
    async def export_outcomes(
        self, *, limit: int = 500, cursor: str | None = None,
    ) -> Page[dict[str, object]]: ...
    async def labeled_outcomes_count(self) -> int: ...
    async def delete_expired(self, *, batch_size: int = 500) -> int: ...
