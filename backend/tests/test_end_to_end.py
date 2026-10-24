"""Real PostgreSQL API journey; provider fixture isolates deterministic contract behavior."""

from __future__ import annotations

import os
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.config import Config
from app.main import create_app
from app.provider import AIResult, Extraction, Generation, Relevance, SourceSummary


class ProviderFixture:
    def __init__(self):
        self.full_contents: list[list[str]] = []

    async def close(self):
        pass

    async def summarize(self, **kwargs):
        return AIResult(SourceSummary(summary="A reference about user interface testing.", tags=["ui testing"]))

    async def embed(self, **kwargs):
        return AIResult([1.0] + [0.0] * (kwargs["dimensions"] - 1))

    async def embed_many(self, **kwargs):
        return AIResult([[1.0] + [0.0] * (kwargs["dimensions"] - 1) for _ in kwargs["texts"]])

    async def extract(self, **kwargs):
        return AIResult(Extraction(tags=["ui testing"], task_type="coding", missing_constraints=["framework"]))

    async def relevance(self, **kwargs):
        return AIResult(Relevance(include=True))

    async def generate(self, **kwargs):
        self.full_contents.append(kwargs["knowledge"])
        return AIResult(Generation(type="none"))


@pytest.mark.integration
def test_persisted_preview_save_retrieve_activity_and_outcome():
    dsn = os.getenv("TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("TEST_DATABASE_URL is not set")
    provider = ProviderFixture()
    app = create_app(
        config=Config(dsn, "fixture", "gemini-embedding-001", 768, "http://localhost"),
        provider=provider,
    )
    marker = uuid4().hex
    with TestClient(app) as client:
        assert client.get("/health").json()["dependencies"]["database"] == "ready"
        preview = client.post("/v1/knowledge/preview", json={
            "title": f"Source {marker}", "kind": "skill", "content": f"Reference content {marker}",
        })
        assert preview.status_code == 200, preview.json()
        preview_id = preview.json()["preview_id"]
        save = client.post("/v1/knowledge", json={"preview_id": preview_id, "idempotency_key": marker})
        assert save.status_code == 201, save.json()
        knowledge_id = save.json()["id"]
        retry = client.post("/v1/knowledge", json={"preview_id": preview_id, "idempotency_key": marker})
        assert retry.status_code == 201
        assert retry.json()["id"] == knowledge_id
        library = client.get("/v1/knowledge", params={"q": marker})
        assert library.status_code == 200
        assert any(item["id"] == knowledge_id for item in library.json()["items"])
        assert client.get(f"/v1/knowledge/{knowledge_id}").json()["content"] == f"Reference content {marker}"

        request_id = f"req_{marker}"
        enhancement = client.post("/v1/enhance", json={
            "request_id": request_id, "prompt": "Test the UI", "prompt_revision": 1, "cursor_position": 11,
        })
        assert enhancement.status_code == 200, enhancement.json()
        assert enhancement.json()["type"] == "none"
        sources = client.get(f"/v1/enhancements/{request_id}/sources").json()["sources"]
        assert any(source["id"] == knowledge_id for source in sources)
        assert any(marker in content for batch in provider.full_contents for content in batch)

        event = client.post("/v1/outcomes", json={
            "event_id": f"event_{marker}", "request_id": request_id, "event_type": "observed",
            "observed_result": "helpful",
        })
        assert event.status_code == 201
        repeat = client.post("/v1/outcomes", json={
            "event_id": f"event_{marker}", "request_id": request_id, "event_type": "observed",
            "observed_result": "helpful",
        })
        assert repeat.json() == event.json()
        detail = client.get(f"/v1/activity/requests/{request_id}")
        assert detail.status_code == 200
        assert detail.json()["api_calls"] and detail.json()["ai_calls"]
        assert "Test the UI" not in str(detail.json())
        assert "Reference content" not in str(detail.json())
        settings = client.get("/v1/settings")
        assert settings.status_code == 200
        assert settings.json()["classifier"]["labeled_outcomes"] >= 1
