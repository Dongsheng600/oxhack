# Prompt Enhance integrations

This document describes the implemented v1 boundaries. Runtime commands, schema, and operational limits are in [database.md](database.md); API shapes are in [contracts/http.md](../contracts/http.md). Cloud readiness is reported honestly rather than inferred from installed packages or local tests.

## Codex and MCP

The repository packages a local streamable-HTTP MCP server on `127.0.0.1:8001/mcp`, a plugin manifest, and the `refine-prompt` skill. The bridge offers `open_refinement_panel`, `enhance_prompt`, `enhancement_sources`, `search_knowledge`, `read_knowledge`, `preview_knowledge`, and `save_knowledge`. These tools use the same FastAPI endpoints as the web editor and preserve the explicit user acceptance/import flow.

`open_refinement_panel` returns the standalone editor URL and copy-handoff instruction. The package does not intercept Codex composer keystrokes or claim direct composer insertion. The repository's separate editor implements its own suffix ghost text, multiple-choice diff preview, confirmation, and copy action. Actual embedded third-party Codex panel presentation remains unverified.

The official [plugin architecture](https://developers.openai.com/plugins/concepts/plugins), [MCP quickstart](https://developers.openai.com/plugins/build/app-quickstart), and [UI guide](https://developers.openai.com/plugins/build/chatgpt-ui) provide background for the tool bridge. Their optional UI guidance is insufficient evidence of native Codex composer control. The MCP path remains useful independently of such host extensions.

CopilotKit's SDK is not included: the approved v1 uses a custom separate editor and local HTTP/MCP boundary, without a CopilotKit runtime requirement. Meaningful tests cover the relevant asynchronous provider, stale-response, edit validation, and explicit confirmation behaviors in the application itself. No installed SDK is presented as proof of host support.

## Gemini

`app.provider.GeminiProvider` uses the Google Gen AI SDK for structured extraction, summary/tag generation, relevance, final response generation, and batched text embeddings. Pydantic schemas validate provider structures; application validators enforce the enhancement union, UTF-16 boundaries, nonoverlapping edits, and trusted request identity. Model IDs are configured backend roles and validated against the application's allowlist. Credentials stay in backend environment variables, and operational logs exclude provider bodies.

The default versioned embedding profile uses `gemini-embedding-001` at 768 dimensions with cosine retrieval; query and stored vectors must match the exact active profile. Model/version/dimension changes cannot silently overwrite stored vectors. [Gemini structured output](https://ai.google.dev/gemini-api/docs/structured-output), [Gemini embeddings](https://ai.google.dev/gemini-api/docs/embeddings).

The brief's “Jev” name remains a documented alias for the configurable Gemini relevance role; no additional unverified provider is implemented. A real provider failure returns an error, while successful retrieval with no relevant knowledge still permits general enhancement. Live Gemini evidence is recorded separately from provider-fake unit tests; this document does not claim a live pass before that evidence exists.

## Tiger Data / PostgreSQL

`app.db.PostgresRepository` uses actual asynchronous psycopg PostgreSQL connections, versioned migrations, typed pgvector columns, and a cosine HNSW index. One service stores the intentional knowledge library, summaries, normalized many-to-many tag links, vectors/profile versions, persistent model settings, request provenance, and expiring operational events. The synchronous import transaction publishes complete ready knowledge only after all tags/vectors/links and the idempotency result commit.

Local tests use a real Docker PostgreSQL 16/pgvector service, with isolated schemas and no SQLite fallback. The existing Tiger Data `prompt_enhance` cloud service has been configured through the user's authenticated Tiger CLI, without creating or upgrading a service. Its real TLS connection, migrations `001_initial`/`002_embedding_profile_integrity`, and pgvector 0.8.7 were verified; the database URL is stored only in ignored `.env`. All six repository integration tests passed against isolated schemas on the real cloud service, including concurrency, rollback, retrieval, retention, pagination, and reindex activation. [Tiger Data extensions](https://docs.timescale.com/use-timescale/latest/extensions/), [Tiger Data vector SQL](https://docs.timescale.com/ai/latest/sql-interface-for-pgvector-and-timescale-vector/), [pgvector](https://github.com/pgvector/pgvector).

## Snowflake

The real connector adapter supports structured-feature export through bound `MERGE`, explicit `CREATE SNOWFLAKE.ML.CLASSIFICATION` training, prediction with `!PREDICT`, and native plus independent held-out evaluation. The exported schema is fixed: task category, missing-constraint count, retrieval counts/best score, suggestion type, and model version, with event metadata and explicit observed helpfulness labels kept distinct. It rejects raw-text task categories and excludes prompts, paragraphs, source content, summaries, tags, responses, event labels, and future outcomes from inference features.

The offline target is explicitly **user-reported helpfulness**, not objective quality or acceptance. Training requires real observations, minimum per-class data, an explicit target selection, and grouping of related revisions/duplicates. A grouped temporal test partition, baseline comparison, per-class/slice metrics, and confidence interval make the resulting report reviewable. No classifier is trained or promoted at startup. A missing/unavailable/expired model gives a labeled baseline without invented predictions. Live cloud readiness, training success, and useful classifier quality remain unverified without credentials and real observations.

Exported events and learned artifacts obey the approved lifetime: expired rows are filtered, transient tables use zero Time Travel retention, and cleanup deletes expired events and drops models no later than their earliest training-source expiry. Run one coordinated exporter/training worker; independent concurrent standard-table writers require additional deployment coordination. The CLI loads `.env` as data with python-dotenv and never asks the shell to execute it. Full commands are in [database.md](database.md).

Official interfaces: [Snowflake classification](https://docs.snowflake.com/en/user-guide/ml-functions/classification), [CREATE CLASSIFICATION](https://docs.snowflake.com/en/sql-reference/classes/classification/commands/create-classification), [Python connector bindings](https://docs.snowflake.com/en/developer-guide/python-connector/python-connector-example), [temporary/transient retention](https://docs.snowflake.com/en/user-guide/tables-temp-transient).

## Logging policy and evidence

The user approved metadata-only logging for 30 days. API/AI activity includes IDs, timestamps, roles/models, status, latency, optional token counts, and sanitized codes. Independently observed helpfulness and interaction events remain distinct. Reads suppress expired records before physical cleanup, and the backend's startup/hourly maintenance handles restart catch-up and paginated export. Knowledge content is intentional application data and is never copied into telemetry.

The [OxHack prize page](https://www.mlh.com/events/oxhack-26/prizes) identifies the named integration categories; a local adapter or package alone is not evidence of live vendor use, eligibility, or quality. Release evidence and remaining live-account checks stay explicit in [acceptance.md](acceptance.md).

## Local plugin installation

The portable package is registered via the repository marketplace and installed/enabled as `prompt-enhance@prompt-enhance-local`. Installed manifest, MCP configuration and skill match the source. Real MCP transport was verified independently; refresh Codex or open a new chat if newly installed tools are not visible. See `evidence/plugin-install.json`. Native composer interception remains unavailable in this implementation.
