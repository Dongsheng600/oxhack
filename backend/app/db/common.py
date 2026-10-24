from __future__ import annotations

import base64
import hashlib
import json
import logging
import math
import unicodedata
from datetime import datetime
from functools import wraps
from uuid import UUID

import psycopg

from ..ports import EmbeddingProfileMismatch, RepositoryUnavailable


class MetadataOnlyPoolFilter(logging.Filter):
    """Driver pool errors may contain DSNs; retain only a fixed operational code."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = "postgres_pool_event"
        record.args = ()
        record.exc_info = None
        record.exc_text = None
        record.stack_info = None
        return True


def canonical_tag(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


def vector_literal(values: list[float], dimensions: int) -> str:
    if len(values) != dimensions or any(
        not isinstance(x, (float, int)) or isinstance(x, bool) or not math.isfinite(x) for x in values
    ):
        raise EmbeddingProfileMismatch("Embedding vector dimension or values are invalid")
    if not any(values):
        raise EmbeddingProfileMismatch("Cosine vectors must have nonzero magnitude")
    return "[" + ",".join(str(float(x)) for x in values) + "]"


def encode_cursor(timestamp: datetime, identifier: str) -> str:
    return (
        base64.urlsafe_b64encode(json.dumps([timestamp.isoformat(), identifier]).encode())
        .decode()
        .rstrip("=")
    )


def decode_cursor(cursor: str | None, *, uuid_id: bool = False) -> tuple[datetime, str] | None:
    if not cursor:
        return None
    try:
        timestamp, identifier = json.loads(base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)))
        parsed = datetime.fromisoformat(timestamp)
        if not parsed.tzinfo or not isinstance(identifier, str):
            raise ValueError
        if uuid_id:
            UUID(identifier)
        return parsed, identifier
    except (ValueError, TypeError, json.JSONDecodeError, UnicodeError) as error:
        raise ValueError("Invalid pagination cursor") from error


def database_errors(function):
    @wraps(function)
    async def wrapped(*args, **kwargs):
        try:
            return await function(*args, **kwargs)
        except (psycopg.Error, TimeoutError):
            # Never forward driver exceptions: statement parameters can contain knowledge.
            raise RepositoryUnavailable("Database operation failed") from None

    return wrapped
