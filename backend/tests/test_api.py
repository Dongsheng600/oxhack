from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.config import Config
from app.main import create_app, drain_expired
from app.provider import AIResult, Extraction, Generation


class RepositoryFixture:
    def __init__(self):
        self.activity = []
        self.sources = {}
        self.features = []

    async def open(self):
        pass

    async def close(self):
        pass

    async def health(self):
        return True

    async def delete_expired(self, **kwargs):
        return 0

    async def get_models(self):
        return None

    async def record_activity(self, kind, entry):
        self.activity.append((kind, entry))

    async def retrieve_candidates(self, **kwargs):
        return []

    async def record_sources(self, **kwargs):
        self.sources[kwargs["request_id"]] = kwargs

    async def get_sources(self, request_id):
        record = self.sources.get(request_id)
        return (record["prompt_revision"], record["sources"]) if record else None

    async def record_features(self, features):
        self.features.append(features)

    async def labeled_outcomes_count(self):
        return 0

    async def list_knowledge(self, **kwargs):
        raise RuntimeError("SENSITIVE_INTERNAL_ERROR_MARKER")


class ProviderFixture:
    async def close(self):
        pass

    async def extract(self, **kwargs):
        return AIResult(Extraction(tags=[], task_type="coding", missing_constraints=[]))

    async def embed_many(self, **kwargs):
        return AIResult([[1.0] + [0.0] * (kwargs["dimensions"] - 1) for _ in kwargs["texts"]])

    async def generate(self, **kwargs):
        return AIResult(Generation(type="none"))


class ClassifierFixture:
    configured = True

    def __init__(self, version):
        self.version = version

    async def status(self):
        return "ready"

    async def active_model_version(self):
        return self.version

    async def cleanup(self):
        return 0

    async def export(self, events):
        return 0


def test_enhance_contract_and_metadata_only_activity():
    repo = RepositoryFixture()
    app = create_app(config=Config(None, "fixture", "gemini-embedding-001", 768, "http://localhost"),
                     repository=repo, provider=ProviderFixture())
    with TestClient(app) as client:
        response = client.post("/v1/enhance", json={
            "request_id": "req_42", "prompt": "Sensitive prompt marker", "prompt_revision": 7,
            "cursor_position": 23,
        })
        assert response.status_code == 200
        assert response.json() == {"schema_version": 1, "request_id": "req_42", "prompt_revision": 7, "type": "none"}
        sources = client.get("/v1/enhancements/req_42/sources")
        assert sources.status_code == 200
        assert sources.json() == {"request_id": "req_42", "prompt_revision": 7, "sources": []}
    assert len(repo.activity) >= 3
    assert "Sensitive prompt marker" not in repr(repo.activity)
    assert repo.features[0].task_type == "coding"


def test_missing_dependencies_are_actionable_503():
    app = create_app(config=Config(None, None, "gemini-embedding-001", 768, "http://localhost"))
    with TestClient(app) as client:
        health = client.get("/health")
        assert health.status_code == 503
        assert health.json()["dependencies"]["database"] == "unavailable"
        response = client.post("/v1/enhance", json={
            "request_id": "req_1", "prompt": "Hi", "prompt_revision": 0, "cursor_position": 2,
        })
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "database_unavailable"


def test_invalid_utf16_cursor_is_422():
    app = create_app(config=Config(None, None, "gemini-embedding-001", 768, "http://localhost"))
    with TestClient(app) as client:
        response = client.post("/v1/enhance", json={
            "request_id": "req_1", "prompt": "😀", "prompt_revision": 0, "cursor_position": 1,
        })
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "invalid_input"


def test_unhandled_errors_log_route_template_without_query_or_exception_payload():
    repo = RepositoryFixture()
    app = create_app(config=Config(None, "fixture", "gemini-embedding-001", 768, "http://localhost"),
                     repository=repo, provider=ProviderFixture())
    with TestClient(app) as client:
        response = client.get("/v1/knowledge", params={"q": "SENSITIVE_SEARCH_MARKER"})
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "internal_error"
    assert "SENSITIVE" not in str(response.json())
    assert repo.activity[-1][1].operation == "GET /v1/knowledge"
    assert repo.activity[-1][1].error_code == "internal_error"
    assert "SENSITIVE" not in repr(repo.activity)


def test_classifier_settings_require_verified_active_registry_model():
    config = Config(None, "fixture", "gemini-embedding-001", 768, "http://localhost")
    for version, expected_status in ((None, "baseline"), ("MODEL_1", "active")):
        app = create_app(config=config, repository=RepositoryFixture(), provider=ProviderFixture(),
                         classifier=ClassifierFixture(version))
        with TestClient(app) as client:
            body = client.get("/v1/settings").json()
        assert body["classifier"] == {"status": expected_status, "labeled_outcomes": 0,
                                      "model_version": version}


@pytest.mark.asyncio
async def test_retention_cleanup_drains_every_expired_batch():
    class CleanupRepository:
        def __init__(self):
            self.counts = iter((500, 500, 4, 0))
            self.calls = 0

        async def delete_expired(self, *, batch_size):
            assert batch_size == 500
            self.calls += 1
            return next(self.counts)

    repository = CleanupRepository()
    assert await drain_expired(repository) == 1004
    assert repository.calls == 4
