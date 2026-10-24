from __future__ import annotations

from dataclasses import dataclass
from os import getenv

DEFAULT_MODELS = {
    "extraction": "gemini-3.5-flash-lite",
    "relevance": "gemini-3.5-flash-lite",
    "generation": "gemini-3.6-flash",
    "summary": "gemini-3.5-flash-lite",
}
ALLOWED_MODELS = frozenset({
    "gemini-3.5-flash-lite", "gemini-3.8-flash", "gemini-3.6-flash",
    "gemini-3.1-flash-lite", "gemini-3.1-pro-preview", "gemini-4-argon",
    "gemini-2.5-flash-lite", "gemini-2.5-flash", "gemini-2.5-pro",
})


@dataclass(frozen=True)
class Config:
    database_url: str | None
    gemini_api_key: str | None
    embedding_model: str
    embedding_dimensions: int
    frontend_origin: str
    snowflake_account: str | None = None
    snowflake_user: str | None = None
    snowflake_password: str | None = None
    snowflake_warehouse: str | None = None
    snowflake_database: str | None = None
    snowflake_schema: str | None = None
    snowflake_model_version: str | None = None
    deadline_seconds: float = 60.0
    max_prompt_chars: int = 20_000
    max_source_chars: int = 100_000
    max_distance: float = 0.38
    per_tag_limit: int = 8
    candidate_limit: int = 20
    included_source_limit: int = 5
    reference_context_chars: int = 60_000
    relevance_concurrency: int = 4
    preview_ttl_seconds: int = 3600

    @classmethod
    def from_env(cls) -> Config:
        return cls(
            database_url=getenv("DATABASE_URL") or None,
            gemini_api_key=getenv("GEMINI_API_KEY") or None,
            embedding_model=getenv("GEMINI_EMBEDDING_MODEL", "gemini-embedding-001"),
            embedding_dimensions=int(getenv("EMBEDDING_DIMENSIONS", "768")),
            frontend_origin=getenv("FRONTEND_ORIGIN", "http://127.0.0.1:3000"),
            snowflake_account=getenv("SNOWFLAKE_ACCOUNT") or None,
            snowflake_user=getenv("SNOWFLAKE_USER") or None,
            snowflake_password=getenv("SNOWFLAKE_PASSWORD") or None,
            snowflake_warehouse=getenv("SNOWFLAKE_WAREHOUSE") or None,
            snowflake_database=getenv("SNOWFLAKE_DATABASE") or None,
            snowflake_schema=getenv("SNOWFLAKE_SCHEMA", "PUBLIC"),
            snowflake_model_version=getenv("SNOWFLAKE_MODEL_VERSION") or None,
        )

    def snowflake_connection(self) -> dict[str, str] | None:
        required = (self.snowflake_account, self.snowflake_user, self.snowflake_password,
                    self.snowflake_warehouse, self.snowflake_database, self.snowflake_schema)
        if any(value is None for value in required):
            return None
        return {
            "account": self.snowflake_account,
            "user": self.snowflake_user,
            "password": self.snowflake_password,
            "warehouse": self.snowflake_warehouse,
            "database": self.snowflake_database,
            "schema": self.snowflake_schema,
        }
