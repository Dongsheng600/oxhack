# PostgreSQL, pgvector, and Snowflake

The backend uses `app.db.PostgresRepository`, an asynchronous psycopg connection pool against PostgreSQL with pgvector. There is no production SQLite or memory substitute. The local Compose database uses the pgvector PostgreSQL 16 image. The existing Tiger Data `prompt_enhance` service is also configured and uses the same repository; real TLS readiness, migrations `001_initial`/`002_embedding_profile_integrity`, and pgvector 0.8.7 were verified. Tiger CLI supplied the stored service credential directly into ignored `.env` without printing it or changing the service plan.

## Initialization and schema

Versioned SQL in `database/migrations/` is applied under a PostgreSQL advisory transaction lock and recorded in `schema_migrations`. Migration execution, version registration, policy initialization, and initial embedding profile creation commit together. Restarting application replicas does not reapply an existing migration. SQL files must be packaged at `/app/database/migrations` in Docker or `app/db/sql` in the installed wheel.

Set `DATABASE_URL`, `GEMINI_EMBEDDING_MODEL`, and `EMBEDDING_DIMENSIONS` before first startup. The default is `gemini-embedding-001`, 768 dimensions, cosine distance. Dimensions are substituted only after validating an integer between 1 and 2000, the supported dimensional range of this deployment's vector HNSW index. Existing databases reject a different dimension or a configured model that differs from the active database profile. The application does not silently mix embeddings.

The schema includes:

- `knowledge`: intentional user library content, summary, content digest, version, timestamps, and ready status.
- `tags`, `knowledge_tags`: unique NFKC/casefold/whitespace-normalized names and many-to-many, versioned links.
- `embedding_profiles`, `tag_embeddings`: versioned model/dimension/normalization profiles, one active profile, typed vectors, composite uniqueness, and a cosine HNSW index.
- `knowledge_previews`, `ingestion_results`, `ingestion_failures`: expiring server-side previews, durable idempotency-to-knowledge results, and sanitized failure codes.
- `model_settings`, `policy_decisions`: persistent validated model settings and the metadata-only, 30-day, payloads-off policy.
- `activity_logs`, `request_sources`, `request_features`, `outcome_events`: strictly operational metadata and derived features with bounded expiry.

The current interface saves complete ready versions only. User knowledge is intentionally persistent application data. It is excluded from telemetry. The database contains no raw prompt or generated response column in its activity, feature, outcome, or provenance tables.

## Preview and transactional ingestion

The approved Generate → Preview → Save journey is synchronous. This replaces the earlier asynchronous-job proposal: summary generation happens before creating the server-side preview; tag embedding happens before the short save transaction. A preview never enters retrieval.

Save checks the durable idempotency result before checking preview expiry, so a committed save can be retried after the draft expires or is cleaned up. An advisory lock serializes requests with the same idempotency key, and the preview row is locked while validating the canonical input digest. Reusing a key for different input returns a conflict. A deliberately distinct key may import identical content again; content hashes are recorded without silently discarding a deliberate import.

Inside one transaction, Save inserts the knowledge, normalizes/upserts tags, inserts missing vectors for the exact active profile, creates all unique tag links, and registers the idempotency result. No success is returned before commit. A failure rolls everything back and attempts to record only `INGESTION_FAILED` in a separate transaction. A provider embedding failure happens before this transaction and preserves the preview for retry. Distinct concurrent imports share normalized tags without duplicate tag rows.

## Retrieval and profile changes

Query vectors must have exactly the active profile's model and dimensions, finite numeric values, and nonzero magnitude. For each query vector, retrieval selects a bounded number of nearest tags by cosine distance, applies the configured maximum distance, joins complete ready knowledge summaries, and aggregates the best score (`1 - cosine_distance`). Results deduplicate knowledge IDs/versions and sort by descending score and stable ID/version before the total candidate cap. Full content is fetched only after the application's relevance step.

A same-dimension embedding model/version change uses an explicit backfill:

```sh
PYTHONPATH=backend .venv/bin/python -m app.db.reindex \
  --model NEW_VERSIONED_MODEL --vectors vectors.json
PYTHONPATH=backend .venv/bin/python -m app.db.reindex \
  --model NEW_VERSIONED_MODEL --vectors vectors.json --activate
```

`vectors.json` maps every linked tag name to a vector generated by that exact target model. The command never fabricates embeddings. The first invocation builds an inactive profile; activation verifies coverage of every currently linked tag in the same transaction that switches profiles. In-flight saves/retrievals hold a shared profile lock; activation waits for those operations. Missing coverage aborts the switch. Existing vectors remain under their original profile. After activation, restart the service with the new embedding model configuration. The UI cannot change the embedding profile.

Different dimensions require a separately reviewed database vector-column/index migration or a fresh database plus a complete, verified reindex/import. The current command intentionally rejects dimensional changes rather than changing a typed vector column implicitly.

## Retention and export

Every operational record expires at its event timestamp plus at most 30 days. Reads and exports exclude expired activity, provenance, outcomes, and features immediately, even when physical cleanup is delayed. `delete_expired(batch_size=500)` deletes bounded batches with `FOR UPDATE SKIP LOCKED` from operational tables and expired preview drafts; it never deletes the intentional knowledge library. The backend calls cleanup at startup and periodically afterward, allowing restart catch-up. Configure PostgreSQL backups, WAL archives, infrastructure logs, and secondary sinks consistently before enabling them; the application cannot shorten an independently configured infrastructure backup lifetime.

`export_outcomes(limit=500, cursor=None)` returns a cursor page of unexpired outcomes joined to unexpired structured request features. The cursor is an opaque ascending timestamp/event-ID position. An exporter must continue through every page; repeated exports are safe. No prompts, tag text, summaries, content, or generated responses are exported.

## Snowflake operations

`app.integrations.snowflake.SnowflakeClassifier` uses the real Snowflake Python connector in a worker thread. Backend environment variables configure account, user, password, warehouse, database, schema, and optionally `SNOWFLAKE_MODEL_VERSION`. Credentials never enter browser responses or operational events. Without credentials, status is `not_configured`. Without a live, unexpired, explicitly promoted model, prediction returns an honest `baseline` result with no invented class or probability. Connector failure also falls back to baseline for optional classifier inference. Required Gemini/database failures remain application errors.

The backend's periodic exporter and the CLI use the same adapter. CLI commands load `.env` as data with python-dotenv, preserving already-set environment values; no shell sourcing is needed:

```sh
PYTHONPATH=backend .venv/bin/python -m app.integrations.snowflake status
PYTHONPATH=backend .venv/bin/python -m app.integrations.snowflake export
PYTHONPATH=backend .venv/bin/python -m app.integrations.snowflake cleanup
PYTHONPATH=backend .venv/bin/python -m app.integrations.snowflake train \
  --version v1 --task-groups task-groups.json \
  --label-definition user_reported_helpfulness
PYTHONPATH=backend .venv/bin/python -m app.integrations.snowflake evaluate --version v1
PYTHONPATH=backend .venv/bin/python -m app.integrations.snowflake predict --features features.json
```

Run one export/training worker per deployment. Each adapter serializes its operations. Export uses bound parameters and `MERGE` keyed by event ID, with a fixed feature whitelist. Standard Snowflake tables do not enforce unique constraints, so independently running exporters must not write concurrently. The bounded single-user API process meets this deployment condition; horizontal deployment requires a shared export lock or a dedicated worker.

The adapter rejects an existing permanent export/registry table to avoid extending deletion through Fail-safe. The export and model registry tables are transient with `DATA_RETENTION_TIME_IN_DAYS=0`; transient tables have no Fail-safe. Snowflake's background physical deletion can lag logical deletion. Cleanup deletes expired events and drops expired classifier objects; prediction and evaluation exclude expired registry entries independently of cleanup. A trained model expires at the earliest expiry of any contributing observation. No longer-lived model/dataset retention policy is assumed.

Training is manual, potentially billable, and never runs at application startup. There is no invented training set. Only explicit `observed` events labeled `helpful` or `unhelpful` are training labels. These are subjective user-reported helpfulness observations, not objective quality; `accepted`, `declined`, `stale`, failed, missing, and unknown outcomes are not helpfulness labels. Minimum input is 20 observations per class by default. The operator must explicitly select `user_reported_helpfulness` as the target and supply `task-groups.json`, a mapping of request IDs to related-task/duplicate groups. All revisions and knowledge-derived duplicates of a task must share a group.

Training uses only features available at the classification moment: fixed task taxonomy (`coding`, `writing`, `analysis`, `research`, `planning`, `other`), missing-constraint count, candidate count, relevant count, best retrieval score, suggestion type, and model version. It excludes event type, observed result, timestamps, request IDs, and group keys as inference inputs. A temporal cutoff defines older training groups and later held-out groups; groups spanning the cutoff are excluded, preventing cross-partition task leakage. Both training classes and a nonempty held-out set are required. The report records target/provenance, feature schema, time window, class counts, excluded boundary rows, split definition, held-out accuracy, majority-class baseline accuracy, confusion matrix, class precision/recall/support, task-category slice coverage/accuracy, and a Wilson accuracy interval. Snowflake native random-split evaluation is supplementary. Promotion remains explicit and requires report review; training alone does not enable classifier optimization in the enhancement pipeline.

The official SQL interface is [`CREATE SNOWFLAKE.ML.CLASSIFICATION`](https://docs.snowflake.com/en/sql-reference/classes/classification/commands/create-classification), `!PREDICT`, and `!SHOW_EVALUATION_METRICS`, as described in [Snowflake classification](https://docs.snowflake.com/en/user-guide/ml-functions/classification). Bound connector calls follow [the Python connector documentation](https://docs.snowflake.com/en/developer-guide/python-connector/python-connector-example). Retention handling follows [transient table semantics](https://docs.snowflake.com/en/user-guide/tables-temp-transient). Live cloud compatibility, account privileges, training success, and classification quality are not claimed without credentials and real labeled observations.

## Verification

```sh
DATABASE_URL=postgresql://USER:PASSWORD@HOST:PORT/DATABASE \
  PYTHONPATH=backend .venv/bin/python -m pytest backend/tests/test_database.py -q
PYTHONPATH=backend .venv/bin/python -m pytest backend/tests/test_snowflake.py -q
SNOWFLAKE_LIVE=1 PYTHONPATH=backend .venv/bin/python -m pytest \
  backend/tests/test_snowflake.py -q -k live
```

Database tests create and remove isolated schemas in a real pgvector PostgreSQL instance. They test concurrent retries, normalized many-to-many tags, link-write failure injection and complete rollback, threshold/caps/deduplication, incompatible vectors/profiles, expired-read suppression and physical purge, settings persistence, knowledge/export pagination, distinct feedback labels, and atomic profile activation. Snowflake unit/contract tests inject a connector only in tests and inspect actual generated SQL/bindings, whitelist/privacy enforcement, cold start, expiration, training/evaluation paths, and error sanitization. The opt-in live test checks real account readiness; it does not fabricate a trained model or claim quality.

Verification on 24 October 2026: all six PostgreSQL repository tests passed both against local Docker PostgreSQL/pgvector and the actual configured Tiger Data cloud service using isolated schemas. Nine Snowflake connector contract tests passed; the opt-in live Snowflake test was skipped because no Snowflake account is available.
