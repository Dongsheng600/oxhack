from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.config import Config
from app.errors import ServiceError
from app.ports import CandidateSummary, KnowledgeDetail
from app.provider import AIResult, Extraction, Generation, Relevance
from app.schemas import EnhanceRequest
from app.service import EnhanceService


class FakeRepo:
    def __init__(self, candidates=None):
        self.candidates = candidates or []
        self.ai_calls = []
        self.source_records = []
        self.features = []
        self.loaded = []

    async def get_models(self):
        return None

    async def record_activity(self, kind, entry):
        self.ai_calls.append((kind, entry))

    async def retrieve_candidates(self, **kwargs):
        return self.candidates

    async def get_knowledge(self, knowledge_id):
        self.loaded.append(knowledge_id)
        return KnowledgeDetail(knowledge_id, "Source", "skill", "Summary", ["tag"], 1,
                               datetime.now(UTC), datetime.now(UTC), "ready", "Full content")

    async def record_sources(self, **kwargs):
        self.source_records.append(kwargs)

    async def record_features(self, features):
        self.features.append(features)


class FakeProvider:
    def __init__(self, *, include=True, generation=None, fail=None):
        self.include = include
        self.generation = generation or Generation(type="none")
        self.fail = fail
        self.calls = []

    async def extract(self, *, prompt, model):
        self.calls.append("extract")
        if self.fail == "extract":
            raise ServiceError(503, "gemini_unavailable", "Gemini unavailable", True)
        return AIResult(Extraction(tags=["tag"], task_type="coding", missing_constraints=[]))

    async def embed(self, **kwargs):
        self.calls.append("embed")
        return AIResult([0.0] * kwargs["dimensions"])

    async def embed_many(self, **kwargs):
        self.calls.append("embed_many")
        return AIResult([[0.0] * kwargs["dimensions"] for _ in kwargs["texts"]])

    async def relevance(self, **kwargs):
        self.calls.append("relevance")
        if self.fail == "relevance":
            raise ServiceError(503, "gemini_unavailable", "Gemini unavailable", True)
        return AIResult(Relevance(include=self.include))

    async def generate(self, **kwargs):
        self.calls.append("generate")
        self.knowledge = kwargs["knowledge"]
        if self.fail == "generate":
            raise ServiceError(503, "gemini_unavailable", "Gemini unavailable", True)
        return AIResult(self.generation)


def config():
    return Config(None, "test", "gemini-embedding-001", 3, "http://localhost")


def request():
    return EnhanceRequest(request_id="req", prompt="Build a tool", prompt_revision=3, cursor_position=12)


@pytest.mark.asyncio
async def test_empty_retrieval_proceeds_to_general_generation():
    repo, provider = FakeRepo(), FakeProvider()
    result = await EnhanceService(repo, provider, config()).enhance(request())
    assert result.type == "none"
    assert provider.knowledge == []
    assert repo.source_records[0]["sources"] == []
    assert repo.features[0].candidate_count == 0
    assert len(repo.ai_calls) == 3  # extraction, embedding, generation


@pytest.mark.asyncio
async def test_all_filtered_still_generates_without_loading_content():
    candidate = CandidateSummary("source", "Source", "skill", "Summary", 1, 0.9)
    repo, provider = FakeRepo([candidate]), FakeProvider(include=False)
    result = await EnhanceService(repo, provider, config()).enhance(request())
    assert result.type == "none"
    assert repo.loaded == []
    assert provider.knowledge == []
    assert repo.features[0].relevant_count == 0


@pytest.mark.asyncio
async def test_only_selected_source_content_is_loaded():
    candidate = CandidateSummary("source", "Source", "skill", "Summary", 1, 0.9)
    repo, provider = FakeRepo([candidate]), FakeProvider(include=True)
    await EnhanceService(repo, provider, config()).enhance(request())
    assert repo.loaded == ["source"]
    assert provider.knowledge == ["Full content"]
    assert [source.id for source in repo.source_records[0]["sources"]] == ["source"]


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["extract", "relevance", "generate"])
async def test_provider_failures_are_errors_not_none(failure):
    candidate = CandidateSummary("source", "Source", "skill", "Summary", 1, 0.9)
    repo, provider = FakeRepo([candidate]), FakeProvider(fail=failure)
    with pytest.raises(ServiceError):
        await EnhanceService(repo, provider, config()).enhance(request())
    assert repo.source_records == []
    assert repo.features == []


@pytest.mark.asyncio
async def test_malformed_generation_is_error_not_none():
    repo, provider = FakeRepo(), FakeProvider(generation=Generation(type="autocomplete", insert_at=0, text=" tail"))
    with pytest.raises(ServiceError) as caught:
        await EnhanceService(repo, provider, config()).enhance(request())
    assert caught.value.status_code == 502
    assert repo.source_records == []
