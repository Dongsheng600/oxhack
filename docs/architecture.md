# Prompt Enhance architecture

The approved v1 implementation is a single-user prompt refinement editor, knowledge library, activity viewer, and settings page. The executable HTTP contract is [contracts/http.md](../contracts/http.md); approved visual tokens and page geometry are in [design.md](../design.md). Authentication, RBAC, tenant isolation, knowledge deletion/editing, and arbitrary URL crawling are outside this version.

## Runtime

Next.js/React serves the browser UI and proxies `/api/v1/*` to FastAPI `/v1/*`. The browser receives no Gemini, PostgreSQL, or Snowflake credentials. FastAPI coordinates typed provider calls and persistence through `app.ports.Repository` and the AI provider interface. PostgreSQL with pgvector stores the library, tag relationships, vectors, settings, provenance, and expiring operational metadata. Snowflake is an optional offline derived-feature analysis integration.

The frontend uses the approved React/Next.js stack: TypeScript, Tailwind, TanStack Query, next-themes, Lucide, Mantine hooks, es-toolkit, Sonner, TanStack Virtual, Motion, and resizable panels. Editor state, diff presentation, knowledge, activity, settings, and shared shell have separate modules and colocated styles. The backend uses Python 3.12+, FastAPI, Pydantic, the Google Gen AI SDK, psycopg's async pool, and the Snowflake connector. Production has no mock-success or demo mode; tests inject controlled providers explicitly.

The packaged MCP bridge provides tools for opening the local editor URL, proposing an enhancement, reading provenance, searching/reading knowledge, generating an import preview, and saving an approved preview. It forwards to the same HTTP API and sanitizes upstream failures. The editor is also usable as a standalone local website. Embedded third-party Codex panel presentation and direct Codex composer interception/insertion remain unverified; the package does not claim native composer access. Suggestions appear within the app's own editor and reach Codex through an explicit copy handoff.

## Enhancement and acceptance

`POST /v1/enhance` accepts a request ID, full prompt, nonnegative revision, and a UTF-16 cursor position. Its successful response is exactly schema version 1 and one of `autocomplete`, `multiple_choice`, or `none`, with the original request ID/revision. Provider responses cannot choose those trusted identity fields. Service failures use non-2xx HTTP errors with sanitized codes/messages; they are never represented as `none`.

Positions use UTF-16 code units and half-open edit ranges. Server and client validate bounds, surrogate-pair boundaries, unique choice IDs, nonempty options/edits, overlap, duplicate insertions, and ambiguous shared insertion boundaries. Adjacent replacement ranges are allowed. Autocomplete contains only a suffix at the original prompt end. Selecting an option produces a diff preview; confirmation applies all edits atomically in descending original-offset order. Declining or canceling leaves the prompt unchanged.

Every text mutation increments the local prompt revision. Text and cursor changes invalidate the active request and visible suggestions, cancel pending work where possible, and invalidate an open preview. The client compares the request ID, revision, and local snapshot generation before displaying or applying a result. A response arriving after a later edit/cursor movement cannot revive stale state. The backend never edits the user's prompt.

The enhancement pipeline is:

1. Gemini structured extraction returns bounded normalized candidate tags, a fixed task category, and missing constraints. Tags use NFKC, casefold, and collapsed whitespace consistently with database ingestion.
2. Query tags are embedded as a batch with the active model/profile. PostgreSQL performs cosine nearest-tag retrieval with configurable maximum distance, per-tag limit, and total candidate cap; candidates deduplicate ready knowledge IDs/versions.
3. Bounded concurrent Gemini relevance calls inspect each candidate summary with the prompt. Full content is fetched only for included candidates and checked against the retrieved version.
4. Gemini generation receives the prompt and selected reference content, then returns the exact response union. Structured validation and edit rules run again before any response reaches the user.
5. The backend records metadata-only provenance and derived counts/scores/model versions under the request ID. Raw prompts, provider bodies, retrieved content, summaries, tags, and generated responses are excluded from telemetry.

Successful zero-candidate retrieval or all-excluded relevance filtering proceeds to general enhancement from the prompt. It may clarify goals, constraints, or output format without inventing project facts or user preferences. Missing facts become questions. Extraction, embedding, database, relevance, generation, malformed output, and deadline failures remain explicit errors. The current overall enhancement deadline and caps are configuration values. No infinite retries or fallback to fabricated provider output is permitted.

Retrieved skills, example prompts, and graphs are reference data. They cannot execute tools, change policies, expose credentials, or bypass validation and user confirmation. The brief's unresolved “Jev” reference is implemented as the configurable Gemini relevance role; no separate Jev provider is claimed.

## Knowledge lifecycle and storage

The approved import journey is synchronous **Generate → Preview → Save**, as specified in [contracts/http.md](../contracts/http.md). `POST /v1/knowledge/preview` calls real Gemini summary/tag extraction and stores intentional source content in an expiring server-side draft. A draft is never retrievable as knowledge. Input edits invalidate the browser's preview. Expired previews return an explicit gone error.

`POST /v1/knowledge` accepts only a preview ID and idempotency key. The service checks a durable committed result before draft expiry, then generates document tag embeddings. A short PostgreSQL transaction inserts complete ready knowledge, normalized tags, exact-profile vectors, many-to-many links, and the idempotency result together. Same-key retries return the same committed knowledge; key reuse for different input conflicts. A failed provider operation preserves the preview, and a failed database write rolls back every active knowledge/index/link change. No asynchronous ingestion-job API or partial-ready success exists in v1.

The database uses foreign keys, uniqueness constraints, SHA-256 input/content digests, profile row locks, and advisory idempotency/migration locks. Knowledge summaries/details support bounded cursor pagination and query/kind/tag filtering. Settings persist validated generation-role model assignments; the embedding profile is read-only in the UI. Versioned same-dimension reindex/backfill tooling validates coverage before an atomic profile switch. Different dimensions require a deliberate vector-column/index migration or fresh indexed database. See [database.md](database.md) for schema and commands.

## Activity and retention

The approved policy is **metadata only, 30 days, payloads off**. Activity records include request ID, operation/model, timestamps, status, latency, optional usage counts, and a sanitized error code. Provenance includes source IDs/titles/kinds/versions. Structured outcomes distinguish displayed, accepted, declined, stale, failed, and separately observed helpfulness. Missing/unknown observations stay unknown; acceptance is never silently relabeled quality.

Every operational event has an expiry no later than its event timestamp plus 30 days. Database reads and exports suppress expired logs, features, outcomes, and provenance immediately. Startup and periodic bounded cleanup physically delete expired records and preview drafts, catching up after downtime. Snowflake exports carry the same or shorter expiry; its reads suppress expired models and cleanup drops expired model objects and events. Intentional knowledge-library content and settings are separate application data. Independently configured backups, WAL archives, and secondary sinks need compatible infrastructure retention.

The hourly backend maintenance loop handles PostgreSQL cleanup and paginated Snowflake export/cleanup. Snowflake transient tables disable Time Travel retention and avoid Fail-safe. Run one export/training worker per deployment; a horizontally scaled deployment needs shared worker coordination because standard Snowflake tables do not enforce uniqueness. Driver exception bodies and HTTP access logs containing arbitrary URL/query text are not used as application telemetry.

## Snowflake classifier

The real connector adapter implements idempotent derived-feature export, explicit train/evaluate/predict operations, retention cleanup, and honest unconfigured/cold-start status. It is optional and does not replace required Gemini/retrieval stages. The enhancement request path currently records derived features without making model-dependent optimization decisions.

Training requires real exported `observed` events, an explicitly selected `user_reported_helpfulness` target, minimum labels per class, and operator-supplied grouping of related revisions/duplicates. Only inference-time categorical/numeric features enter the model. A grouped temporal held-out split excludes tasks spanning the cutoff; reports compare against the majority-class baseline and record class metrics, uncertainty, slice coverage, provenance, versions, and time window. Models expire no later than the earliest contributing record. Training does not promote a classifier automatically. An optional trained prediction always remains advisory and cannot bypass prompt confirmation. See [database.md](database.md) for executable commands and lifecycle details.

## Validation status and limits

Real local PostgreSQL/pgvector tests pass for transactional rollback, concurrent idempotency, normalized many-to-many relationships, cosine retrieval, profile mismatch, expiration, settings/pagination, and controlled reindex activation. Snowflake contract tests exercise the connector boundary with a test-only fake, including actual generated SQL/bindings and held-out evaluation logic. The existing Tiger Data `prompt_enhance` service is configured: its real TLS database connection, both application migrations, and pgvector 0.8.7 were verified. All six repository integration tests also passed against isolated schemas on that real Tiger Data cloud service. Live Snowflake connection/training/prediction remain unavailable because no Snowflake account is available; no trained quality is claimed. Gemini live verification is tracked separately and must be recorded from actual provider results. Current journey/fidelity/release evidence belongs in [acceptance.md](acceptance.md).
