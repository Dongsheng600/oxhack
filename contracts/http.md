# Implementation coordination contract

Approved v1 visuals: `design.md` and `design/mockups/`. API base: `/v1` on FastAPI, proxied by Next at `/api/v1`. Secrets live only in backend environment. No mock or demo mode in production. Tests may inject controlled providers.

JSON uses snake_case. Timestamps are ISO 8601 UTC strings. UUID/opaque IDs are strings. Knowledge kinds: `skill`, `prompt`, `graph`. Errors: non-2xx `{error:{code,message,retryable},request_id}`. Pagination: `{items:[],next_cursor:string|null}` with `limit` and opaque `cursor` query parameters. Health `/health` returns dependency readiness truthfully without exposing secrets.

## Refine

`POST /v1/enhance`: `{request_id,prompt,prompt_revision,cursor_position}` → exact union from original brief. Do not add fields to that union. `GET /v1/enhancements/{request_id}/sources` → `{request_id,prompt_revision,sources:[{id,title,kind,version}]}`. Sources are metadata only.

`POST /v1/outcomes`: `{event_id,request_id,event_type,observed_result?}`. event_type = `displayed|accepted|declined|stale|failed|observed`. observed_result = `helpful|unhelpful|unknown`; feedback is not objective quality. Return 201 with `{id}` and stable ID on idempotent retry.

## Knowledge

`GET /v1/knowledge?q=&kind=&tag=&cursor=&limit=` → paged knowledge summaries. Summary: `{id,title,kind,summary,tags:string[],version,created_at,updated_at,status}`.

`GET /v1/knowledge/{id}` → summary plus `content`.

`POST /v1/knowledge/preview`: `{title,kind,content}` → `{preview_id,title,kind,summary,tags:string[],expires_at}`. This calls Gemini; it must never fabricate success. Store source content as intentional application data, not in telemetry. Preview does not enter retrieval until save.

`POST /v1/knowledge`: `{preview_id,idempotency_key}` → persisted knowledge detail (201). This performs transactional knowledge/tag/vector/link ingestion using server-stored preview. Retry is idempotent. Preview input edits invalidate preview in UI. Expired previews return 410; failed summary/embedding/DB operations are errors and preserve user input. No save success before commit. A synchronous preview/save flow matches the approved Generate → Preview → Save user journey; document that choice against earlier asynchronous job proposal.

## Activity

`GET /v1/activity/{api|ai}?status=all|success|error&cursor=&limit=` → paged log entries `{id,request_id,timestamp,operation,model:string|null,status:string,status_code:number|null,latency_ms:number,input_tokens:number|null,output_tokens:number|null,error_code:string|null}`.

`GET /v1/activity/requests/{request_id}` → `{request_id,api_calls:[entry],ai_calls:[entry],sources:[{id,title,kind,version}],expires_at}`. Never include prompts or model/knowledge payloads. Logs are metadata-only, 30-day expiry enforced on reads and cleanup.

## Settings

`GET /v1/settings` → `{models:{extraction,relevance,generation,summary,embedding},embedding_dimensions:number,providers:{gemini:{configured:boolean,status:string},database:{configured:boolean,status:string},snowflake:{configured:boolean,status:string}},logging:{mode:"metadata_only",retention_days:30,payloads:false},classifier:{status:string,labeled_outcomes:number,model_version:string|null}}`.

`PATCH /v1/settings` accepts `{models?:{extraction?,relevance?,generation?,summary?}}`, validates allowed Gemini model identifiers and persists. Embedding profile is read-only in UI; model/dimension changes use a controlled migration/reindex command. Theme is an explicit local UI preference, not telemetry.

## Agent boundaries

- Frontend agent owns `frontend/` only; implements all routes, typed client, editor semantics, colocated styles and meaningful tests.
- Backend agent owns `backend/` except DB and Snowflake files assigned below; defines config, API schemas/routes, Gemini orchestration, errors, logging and tests. Coordinates repository protocol with DB agent directly.
- DB/integration agent owns `backend/app/db/`, `backend/app/integrations/snowflake.py`, `backend/tests/test_database.py`, `backend/tests/test_snowflake.py`, `database/`, `docs/database.md` only. Implements real PostgreSQL/pgvector persistence, retention, retrieval and Snowflake export/train/evaluate/predict interface.
- Main orchestrator owns root infrastructure, shared contracts, plugin packaging/MCP bridge, docs and final evidence. All agents share one checkout. Do not overwrite another owner's files. Accommodate concurrent edits. Main exclusively controls browser/CUA.
