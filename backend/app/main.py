"""FastAPI entry point. Responses and operational logs never expose input payloads."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from time import perf_counter
from typing import Any, Literal
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import ALLOWED_MODELS, Config
from .errors import ServiceError, unavailable
from .integrations.snowflake import SnowflakeClassifier
from .ports import (
    ActivityEntry,
    EmbeddingProfileMismatch,
    IdempotencyConflict,
    OutcomeEvent,
    PreviewExpired,
    PreviewMissing,
    Repository,
    RepositoryUnavailable,
)
from .provider import AIProvider, GeminiProvider
from .schemas import EnhanceRequest, OutcomeRequest, PreviewRequest, SaveKnowledgeRequest, SettingsPatch
from .service import RETENTION, EnhanceService, utc_now


def _error_response(error: ServiceError, request_id: str) -> JSONResponse:
    return JSONResponse(
        status_code=error.status_code,
        content={"error": {"code": error.code, "message": error.message, "retryable": error.retryable}, "request_id": request_id},
    )


def _activity_public(entry: ActivityEntry) -> dict[str, Any]:
    return {
        "id": entry.id, "request_id": entry.request_id,
        "timestamp": entry.timestamp, "operation": entry.operation,
        "model": entry.model, "status": entry.status,
        "status_code": entry.status_code, "latency_ms": entry.latency_ms,
        "input_tokens": entry.input_tokens, "output_tokens": entry.output_tokens,
        "error_code": entry.error_code,
    }


def _mapped_error(error: Exception) -> ServiceError:
    if isinstance(error, ServiceError):
        return error
    if isinstance(error, RepositoryUnavailable):
        return unavailable("database")
    if isinstance(error, PreviewMissing):
        return ServiceError(404, "preview_not_found", "The preview was not found. Generate a new preview.")
    if isinstance(error, PreviewExpired):
        return ServiceError(410, "preview_expired", "The preview expired. Generate it again before saving.")
    if isinstance(error, IdempotencyConflict):
        return ServiceError(409, "idempotency_conflict", "This save key was already used for another source.")
    if isinstance(error, EmbeddingProfileMismatch):
        return ServiceError(503, "embedding_profile_mismatch", "The embedding profile does not match stored vectors. Reindex before retrying.")
    if isinstance(error, asyncio.TimeoutError):
        return ServiceError(504, "deadline_exceeded", "The request timed out. Retry it.", True)
    if isinstance(error, HTTPException):
        return ServiceError(error.status_code, "not_found" if error.status_code == 404 else "http_error", "The requested item was not found." if error.status_code == 404 else "The request could not be completed.")
    return ServiceError(500, "internal_error", "The request failed. Retry or check service health.", True)


async def drain_expired(repository: Repository, *, batch_size: int = 500) -> int:
    deleted = 0
    while True:
        count = await repository.delete_expired(batch_size=batch_size)
        deleted += count
        if count == 0:
            return deleted
        await asyncio.sleep(0)


def create_app(
    *, config: Config | None = None,
    repository: Repository | None = None,
    provider: AIProvider | None = None,
    classifier: SnowflakeClassifier | None = None,
) -> FastAPI:
    config = config or Config.from_env()
    if repository is None and config.database_url:
        from .db import PostgresRepository
        repository = PostgresRepository(
            config.database_url.replace("postgresql+psycopg://", "postgresql://", 1),
            embedding_model=config.embedding_model,
            embedding_dimensions=config.embedding_dimensions,
        )
    provider = provider or GeminiProvider(config.gemini_api_key)
    service = EnhanceService(repository, provider, config) if repository is not None else None
    classifier = classifier or SnowflakeClassifier(
        connect_kwargs=config.snowflake_connection(),
        model_version=config.snowflake_model_version,
    )

    async def cleanup_loop() -> None:
        while True:
            try:
                if repository is not None:
                    await drain_expired(repository)
                    if classifier.configured:
                        cursor = None
                        while True:
                            page = await repository.export_outcomes(limit=500, cursor=cursor)
                            await classifier.export(page.items)
                            if page.next_cursor is None:
                                break
                            cursor = page.next_cursor
            except Exception:  # noqa: BLE001, S110 - cleanup must survive DB outages.
                # Errors are visible through dependency health. Never print DB details.
                pass
            try:
                if classifier.configured:
                    await classifier.cleanup()
            except Exception:  # noqa: BLE001, S110 - expiry cleanup retries after outages.
                pass
            await asyncio.sleep(3600)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.repo_ready = False
        if repository is not None:
            try:
                await repository.open()
                app.state.repo_ready = await repository.health()
            except Exception:  # noqa: BLE001 - app remains available for health diagnostics.
                app.state.repo_ready = False
        cleanup = asyncio.create_task(cleanup_loop())
        try:
            yield
        finally:
            cleanup.cancel()
            try:
                await cleanup
            except asyncio.CancelledError:
                pass
            await provider.close()
            if repository is not None:
                await repository.close()

    app = FastAPI(title="Prompt Enhance API", version="1.0.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware, allow_origins=[config.frontend_origin], allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH"], allow_headers=["Content-Type"],
    )

    def repo_required() -> Repository:
        if repository is None:
            raise unavailable("database")
        return repository

    def service_required() -> EnhanceService:
        if service is None:
            raise unavailable("database")
        return service

    @app.exception_handler(RequestValidationError)
    async def validation_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        request.state.error_code = "invalid_input"
        return _error_response(ServiceError(422, "invalid_input", "The request has invalid fields or UTF-16 offsets."), getattr(request.state, "request_id", ""))

    @app.exception_handler(Exception)
    async def exception_handler(request: Request, exc: Exception) -> JSONResponse:
        error = _mapped_error(exc)
        request.state.error_code = error.code
        return _error_response(error, getattr(request.state, "request_id", ""))

    @app.middleware("http")
    async def metadata_middleware(request: Request, call_next):
        request.state.request_id = str(uuid4())
        started_at = utc_now()
        started = perf_counter()
        try:
            response = await call_next(request)
        except Exception as exc:  # noqa: BLE001 - sanitize every unexpected exception.
            error = _mapped_error(exc)
            request.state.error_code = error.code
            response = _error_response(error, request.state.request_id)
        if request.url.path.startswith("/v1/") and repository is not None:
            route = request.scope.get("route")
            operation = f"{request.method} {route.path}" if route is not None else f"{request.method} unmatched_route"
            entry = ActivityEntry(
                id=str(uuid4()), request_id=request.state.request_id,
                timestamp=started_at, operation=operation,
                model=None, status="success" if response.status_code < 400 else "error",
                status_code=response.status_code,
                latency_ms=round((perf_counter() - started) * 1000),
                input_tokens=None, output_tokens=None,
                error_code=getattr(request.state, "error_code", None),
                expires_at=started_at + RETENTION,
            )
            try:
                await repository.record_activity("api", entry)
            except Exception:  # noqa: BLE001, S110 - response has already been generated.
                # A DB outage can make telemetry unavailable; don't leak it in a body.
                pass
        return response

    async def database_ready() -> bool:
        if repository is None:
            return False
        try:
            return await repository.health()
        except Exception:  # noqa: BLE001 - health must never expose DB errors.
            return False

    async def snowflake_status() -> tuple[bool, str]:
        try:
            return classifier.configured, await classifier.status()
        except Exception:  # noqa: BLE001 - optional integration health is sanitized.
            return False, "unavailable"

    @app.get("/health")
    async def health():
        db_ok = await database_ready()
        gemini_ok = bool(config.gemini_api_key)
        snowflake_configured, snowflake_state = await snowflake_status()
        return JSONResponse(
            status_code=200 if db_ok and gemini_ok else 503,
            content={"status": "ready" if db_ok and gemini_ok else "not_ready",
                     "dependencies": {"database": "ready" if db_ok else "unavailable",
                                      "gemini": "configured" if gemini_ok else "not_configured",
                                      "snowflake": snowflake_state if snowflake_configured else "not_configured"}},
        )

    @app.post("/v1/enhance")
    async def enhance(payload: EnhanceRequest, request: Request):
        request.state.request_id = payload.request_id
        response = await service_required().enhance(payload)
        return response

    @app.get("/v1/enhancements/{request_id}/sources")
    async def enhancement_sources(request_id: str):
        data = await repo_required().get_sources(request_id)
        if data is None:
            raise HTTPException(404)
        revision, sources = data
        return jsonable_encoder({"request_id": request_id, "prompt_revision": revision, "sources": sources})

    @app.post("/v1/outcomes", status_code=201)
    async def outcome(payload: OutcomeRequest, request: Request):
        request.state.request_id = payload.request_id
        now = utc_now()
        outcome_id = await repo_required().record_outcome(OutcomeEvent(
            event_id=payload.event_id, request_id=payload.request_id,
            event_type=payload.event_type, observed_result=payload.observed_result,
            timestamp=now, expires_at=now + RETENTION,
        ))
        return {"id": outcome_id}

    @app.get("/v1/knowledge")
    async def list_knowledge(
        q: str | None = None, kind: Literal["skill", "prompt", "graph"] | None = None,
        tag: str | None = None, cursor: str | None = None,
        limit: int = Query(20, ge=1, le=100),
    ):
        return jsonable_encoder(await repo_required().list_knowledge(q=q, kind=kind, tag=tag, cursor=cursor, limit=limit))

    @app.get("/v1/knowledge/{knowledge_id}")
    async def knowledge_detail(knowledge_id: str):
        detail = await repo_required().get_knowledge(knowledge_id)
        if detail is None:
            raise HTTPException(404)
        return jsonable_encoder(detail)

    @app.post("/v1/knowledge/preview")
    async def preview(payload: PreviewRequest, request: Request):
        record = await service_required().preview(payload, request.state.request_id)
        return jsonable_encoder({
            "preview_id": record.preview_id, "title": record.title, "kind": record.kind,
            "summary": record.summary, "tags": record.tags, "expires_at": record.expires_at,
        })

    @app.post("/v1/knowledge", status_code=201)
    async def save_knowledge(payload: SaveKnowledgeRequest, request: Request):
        detail = await service_required().save(
            preview_id=payload.preview_id, idempotency_key=payload.idempotency_key,
            request_id=request.state.request_id,
        )
        return jsonable_encoder(detail)

    @app.get("/v1/activity/requests/{request_id}")
    async def request_activity(request_id: str):
        data = await repo_required().request_activity(request_id)
        if data is None:
            raise HTTPException(404)
        api_calls, ai_calls, sources, expires_at = data
        return jsonable_encoder({
            "request_id": request_id, "api_calls": [_activity_public(entry) for entry in api_calls],
            "ai_calls": [_activity_public(entry) for entry in ai_calls],
            "sources": sources, "expires_at": expires_at,
        })

    @app.get("/v1/activity/{kind}")
    async def activity(
        kind: Literal["api", "ai"], status: Literal["all", "success", "error"] = "all",
        cursor: str | None = None, limit: int = Query(20, ge=1, le=100),
    ):
        page = await repo_required().list_activity(kind=kind, status=status, cursor=cursor, limit=limit)
        return jsonable_encoder({"items": [_activity_public(entry) for entry in page.items], "next_cursor": page.next_cursor})

    @app.get("/v1/settings")
    async def settings():
        models = await service_required().models()
        db_ok = await database_ready()
        snowflake_configured, snowflake_state = await snowflake_status()
        active_classifier = await classifier.active_model_version() if snowflake_state == "ready" else None
        classifier_status = (
            "active" if active_classifier else
            "baseline" if snowflake_state == "ready" else
            "unavailable" if snowflake_configured else "disabled"
        )
        return {
            "models": {**models, "embedding": config.embedding_model},
            "embedding_dimensions": config.embedding_dimensions,
            "providers": {
                "gemini": {"configured": bool(config.gemini_api_key), "status": "configured" if config.gemini_api_key else "not_configured"},
                "database": {"configured": bool(config.database_url or repository), "status": "ready" if db_ok else "unavailable"},
                "snowflake": {"configured": snowflake_configured, "status": snowflake_state},
            },
            "logging": {"mode": "metadata_only", "retention_days": 30, "payloads": False},
            "classifier": {"status": classifier_status,
                           "labeled_outcomes": await repo_required().labeled_outcomes_count(),
                           "model_version": active_classifier},
        }

    @app.patch("/v1/settings")
    async def update_settings(payload: SettingsPatch):
        updates = payload.models.model_dump(exclude_none=True) if payload.models else {}
        if not updates:
            raise ServiceError(422, "invalid_models", "Provide at least one model role to update.")
        if any(model not in ALLOWED_MODELS for model in updates.values()):
            raise ServiceError(422, "invalid_models", "One or more Gemini model identifiers are not allowed.")
        await repo_required().set_models(updates)
        return await settings()

    return app


app = create_app()
