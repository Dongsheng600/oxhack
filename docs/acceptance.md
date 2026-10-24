# Prompt Enhance acceptance matrix

Status: implementation verified on 24 October 2026 after explicit mockup approval. Results and limits below distinguish real cloud checks from deterministic test fixtures. `design.md` controls visuals; `contracts/http.md` controls HTTP behavior. Snowflake live training is deferred because the user cannot create an account; the app remains usable with its truthful disabled state.

## Evidence rules

Every implemented row needs a reproducible check, actual result, and artifact or command reference. Use real backend/provider/database integrations for integration acceptance; provider fixtures are useful for deterministic edge tests but cannot demonstrate live integration. No static success screens, decorative controls, or unpersisted browser-only state satisfy a required behavior. Retry affected checks and regressions after fixing failures. The evidence map below records completed checks and remaining integration limits.

## Pages and interaction families

| ID | Surface or journey | Pass condition | Evidence requirement |
| --- | --- | --- | --- |
| D01 | Complete design gate | All inventoried pages/tabs and material states have coherent desktop/mobile rendered mockups, a contact sheet, individual images, realistic content, and documented tokens; user explicitly approves the complete current set. | Mockup inventory, image links, approval message. |
| D02 | Content discipline | No page subtitles, card blurbs, decorative captions, or filler helper sentences. Labels, actual product data, accessible names, diff content, and actionable errors remain. Required content conflicts are resolved explicitly. | Visual/content inspection of every mockup and final page. |
| R01 | Refine: editor | Typing, paste, selection, cursor movement, undo/redo, and clearing work; prompt survives recoverable service errors. Revision changes on every text mutation. | Browser interaction check; editor state assertions. |
| R02 | Refine: autocomplete | Valid suffix appears as ghost text at prompt end without changing editor value; explicit acceptance inserts once as one undoable operation; dismiss leaves text untouched. Cursor away from end suppresses ghost text under the implemented policy. | Browser assertions and real response trace. |
| R03 | Refine: choices | Question has at least two uniquely identified options; choosing an option opens its diff; no editor mutation before confirmation. Confirm applies the selected edits atomically; decline all/cancel leaves text unchanged. | Interaction recording and state assertions. |
| R04 | Refine: diff | Insertions, deletions, and replacements show accurate before/after content; multiple edits use original snapshot offsets and apply from end to beginning as one undo step. | Multi-edit fixture plus browser confirmation check. |
| R05 | Refine: none | Successful `none` shows a restrained valid state, clears older suggestions, leaves prompt unchanged, and is distinguishable from failure. | Real no-suggestion outcome or controlled contract test plus UI assertion. |
| R06 | Refine: failure/retry | Timeout, unavailable dependency, malformed result, and rate limit show actionable error/retry controls without losing the prompt or pretending success. Retry gets a fresh request ID; stale errors cannot overwrite a newer result. | Injected failure checks and one real dependency-failure trace. |
| K01 | Knowledge library | Real stored knowledge loads, searches/filters, paginates, and opens detail; empty and load-failure states are usable; long lists remain navigable. | API/database-backed browser journey. |
| K02 | Knowledge detail | Correct title, content, summary, tags, kind, source, and version appear from the persisted item; retrieval state matches ingestion state. Untrusted markdown/content cannot execute code. | Persisted sample inspection and malicious-content test. |
| K03 | Add knowledge | Valid content generates a real expiring preview; explicit Save source transactionally stores the approved preview and opens its persisted detail. Invalid input and failure show actionable errors; retry cannot duplicate imports. | Real Gemini/Tiger Data import followed by reload and database checks. |
| A01 | Activity: API tab | Shows actual API metadata with request ID, timestamp, operation, status, latency, and sanitized failure detail; filters, pagination, empty/error states, and detail interactions work. | Correlated live calls and metadata inspection. |
| A02 | Activity: AI tab | Shows actual role/model metadata and available token counts; connects multiple AI calls to the right API request; unavailable usage is represented honestly. Tab switch preserves valid filtering behavior. | Live multi-stage trace and UI verification. |
| S01 | Settings: models | Role assignments, validation, save feedback, and persistence work; credential presence never exposes secret values. Active embedding changes require a versioned reindex/switch flow rather than mixing vectors. | Reload, invalid-save check, configuration/database evidence. |
| S02 | Settings: logging | Shows the user-approved “Metadata only” and “30 days” policy; payload logging stays OFF. API/AI logs and operational outcome/feature events follow that lifetime; no implicit unlimited retention or longer-lived training dataset is introduced. | Policy record, settings UI, backend/log inspection. |
| U01 | Navigation and controls | Every page/tab and button has a working destination/action; active navigation, dialogs, menus, selects, filters, notifications, and resizable panels behave consistently. No visible decorative controls. | Route/control inventory with browser checks. |
| U02 | Responsive | Each page/tab works at approved desktop/mobile sizes; panel/sidebar adaptations preserve access; long prompts, diffs, tags, tables, and dialogs do not cause clipped actions or page overflow. | Browser-rendered screenshots at approved widths. |
| U03 | Keyboard and access | Editor, choices, diff confirmation/cancel, add dialog, tabs, filters, and settings are keyboard accessible; focus is visible, dialog focus returns correctly, errors are announced, and shortcuts do not hijack text entry/IME. | Keyboard journey and accessibility checks. |
| U04 | Theme | Light, dark, and system behavior follow approved tokens; preference persists; ghost text, diff additions/deletions, focus, disabled, loading, and error states remain legible. | Screenshots and contrast checks in both themes. |
| U05 | Fidelity | Actual page geometry, typography, color, spacing, icons, and interaction states match approved designs; material visual revisions return to approval. | Side-by-side rendered comparison across inventory. |

## Contract, race, and edit safety

| ID | Scenario | Pass condition | Evidence requirement |
| --- | --- | --- | --- |
| C01 | Exact contract | All three response variants use `schema_version: 1`, request ID/revision, and only valid branch fields; client/server reject unsupported versions or malformed payloads. Errors use HTTP error responses. | Schema/route contract checks. |
| C02 | UTF-16 offsets | Astral characters, combining text, and mixed scripts preserve UTF-16 bounds; Python conversion agrees with JavaScript. Half-open ranges, insertion, and deletion behave as specified; surrogate-splitting edits are rejected under the implemented stricter rule. | Cross-language fixtures, including emoji before/inside edits. |
| C03 | Edit validation | Out-of-bounds, reversed, noninteger, overlapping, duplicate-insertion, ambiguous-boundary edits, empty option lists, duplicate option IDs, and options without edits are rejected; valid adjacent replacements succeed. | Validator cases and browser rejection checks. |
| C04 | Out-of-order text race | Request A returns after B, or prompt changes before response; only the latest matching request/revision/snapshot can display or apply. Abort failure does not weaken safety. | Deterministically delayed responses. |
| C05 | Cursor race | Cursor moves without a revision change, including away and back; the old ID/local generation remains invalid, old ghost text/questions/previews disappear, and delayed responses cannot revive them. | Cursor-only delayed-response test. |
| C06 | Confirm race | Text/cursor changes while a diff is open invalidate it; confirmation rechecks snapshot and cannot apply stale edits or create a partial change. | Interleaved editor/confirm interaction. |
| C07 | Autocomplete constraints | `insert_at` equals original UTF-16 prompt length; response is suffix only; wrong insertion point is rejected and acceptance does not duplicate existing text. | Contract/interaction check. |
| C08 | No suggestion versus failure | Successful zero candidates or all exclusions can yield general enhancement/`none`; DB, embedding, relevance, extraction, and generation failures produce errors rather than a false empty result. | Pipeline branch tests and failure injection. |

## Backend, database, and integrations

| ID | Scenario | Pass condition | Evidence requirement |
| --- | --- | --- | --- |
| B01 | Real Gemini pipeline | Extracts typed tags/features, embeds query tags, judges each candidate summary, generates a valid response; role/model versions are attributable. “Jev” alias is resolved or remains explicitly documented as provisional. | Sanitized live integration trace and dependency documentation. |
| B02 | Retrieval and deduplication | Configured metric/threshold/caps retrieve matching tags, join many-to-many knowledge, and deduplicate candidate IDs/versions deterministically; only ready complete knowledge is eligible. | Seeded database scenario with expected candidate IDs. |
| B03 | General enhancement | Zero candidate and all-excluded cases both proceed successfully without inventing project facts, sources, or preferences; unresolved information can become choices; `none` is valid when no improvement is useful. | Curated scenarios and human assessment of real outputs. |
| B04 | Reference-data boundary | Malicious instructions inside a SKILL/example/graph cannot invoke tools, expose secrets, alter response schema, auto-apply edits, or bypass confirmation. Full content is loaded only after summary relevance selection. | Adversarial fixtures and pipeline trace. |
| B05 | Transactional ingestion | Knowledge content/summary/version, tags, embeddings, and links become ready together. Failure at each write point exposes no partial ready import and returns a sanitized error and preserves the draft. | Transaction failure-injection and database assertions. |
| B06 | Idempotency and concurrency | Repeating same key/input returns same saved result; same key/different input returns 409; simultaneous imports normalize shared tags without duplicates; concurrent retries cannot publish duplicate knowledge. | Concurrent request/database test. |
| B07 | Vector profiles | Stored/query model versions and dimensions match; mismatches fail explicitly; reindex builds a separate profile and switches only after validated coverage; in-flight requests retain consistent profiles. | Migration/backfill/active-switch checks. |
| B08 | Persistence | Knowledge, relations, summaries, configuration, and approved event metadata survive service/browser restart; no success claim relies solely on local state. | Restart/reload and database reads. |
| B09 | Errors and deadlines | Input errors, provider malformed output, limits, dependency failure, and timeout map to actionable statuses; bounded retries stop at deadline; no provider payload/secrets leak. | API error matrix and trace review. |
| B10 | Secrets and logging | Browser bundle/network responses/storage and all logs contain no credentials; exceptions/debug logs exclude raw prompts, knowledge, summaries, tag text, and generated responses while payload logging is OFF. | Seeded secret/payload markers plus log/bundle inspection. |
| B11 | Metadata and policy | API/AI events correlate by request ID, truthful times/status/latency/token availability, and model/config versions. At 30 days, API/AI logs and operational outcome/feature events disappear from reads/exports; cleanup purges them from Tiger Data and Snowflake, catches up after restarts, and covers secondary copies. Longer-lived training datasets/aggregates need a separate decision. | Approved policy record and time-controlled lifecycle/cleanup checks. |
| B12 | Snowflake derived inputs | Classification consumes versioned structured features, without raw paragraphs; event exports are idempotent; credentials remain backend-only. | Real exported feature sample and live classification call. |
| B13 | Classifier validity | Target, label provenance, training window, related-task grouping/time splits, leakage prevention, baseline, held-out metrics, and model version are documented; acceptance is never silently labeled quality. | Reproducible real train/evaluate artifact and model registration. |
| B14 | Cold start and outage | Baseline/disabled optimization is truthfully labeled before enough data; unavailable classifier follows the declared fallback without masking required pipeline failures or removing user acceptance. | Cold-start and classifier-failure scenarios. |
| B15 | Outcomes | Displayed, accepted, declined, stale, failed, and independently observed results remain distinct; missing outcome is unknown; duplicate event IDs do not double-count. | Event schema/duplicate/label-provenance checks. |
| B16 | Host and CopilotKit claims | Standalone panel works; supported Codex host/composer access is verified before claiming it; SDK is included only if approved features need it. Relevant CopilotKit test patterns are documented/applied after approval. | Current primary docs, actual host journey, dependency/test rationale. |

## Executed evidence map

| Rows | Result | Executed evidence and limit |
| --- | --- | --- |
| D01–D02 | PASS | Explicit user approval; 39 approved images in design/mockups; final rendered comparison in ../design-qa.md. |
| R01–R06 | PASS | 33 frontend tests plus browser typing, keyboard acceptance, Undo, choice/diff/confirm, copy, decline, none, error/recovery. Production Gemini returned real autocomplete/choice; deterministic edge states use test-only provider. |
| K01–K03 | PASS | Browser search/type filter, preview/save/detail/reload and failed-preview recovery; real Gemini summary/embeddings and Tiger Data transaction in ../evidence/live-gemini.json. Empty browser capture is a filtered empty result; empty-store behavior also covered by component tests. |
| A01–A02 | PASS | Browser API/AI tabs, error filter, pagination, correlated request detail; real cloud AI activity includes measured usage where available. |
| S01–S02 | PASS | Browser rejects invalid model, persists valid selection across reload; read-only embedding profile; logging policy visible; expiry and cleanup tests. |
| U01–U05 | PASS | Navigation/control journeys; 39 full-page captures at1280/390/560px with zero horizontal overflow; light/dark plus system preference; keyboard tests and visible focus. No dedicated screen-reader audit was performed. |
| C01–C08 | PASS | backend/tests/test_contract.py and test_service.py; frontend tests cover UTF-16, malformed edits, stale response/cursor races, accept/undo and confirmation. |
| B01–B03 | PASS | Live Gemini/Tiger source selection and final generation; earlier live zero-candidate/all-excluded runs; deterministic retrieval thresholds/dedupe/profile tests on real PostgreSQL. |
| B04 | PASS (structural boundary) | Provider receives source content as reference data, has no tool execution capability, outputs undergo schema/edit validation, and client requires acceptance. Code review and selected-source tests verify those boundaries; no claim of universal model-level prompt-injection immunity. |
| B05–B08 | PASS | Six repository integration tests pass both locally and on hosted Tiger Data; include rollback, concurrency, profile switch, settings/outcomes and persisted reads. Browser source detail survives reload. |
| B09–B11 | PASS | Error/deadline, payload marker, unexpected500, pool-secret redaction, read suppression and multi-batch cleanup regressions. External backup/WAL retention remains infrastructure configuration, outside application log storage. |
| B12–B13 | DEFERRED live | Snowflake derived-feature/export/train/evaluate/predict contract tests pass; no account, real labeled corpus, live model or evaluated classifier exists. The user explicitly reported no Snowflake account. |
| B14–B15 | PASS | Disabled/baseline state, registered-model checks, true observed-label distinction and event idempotency tested. |
| B16 | PASS package/transport/install | Real MCP initialize/list/call smoke passed; companion editor opens in Codex browser. Portable package installed and enabled; copied manifests/skill match the source. Native composer override is not claimed; desktop refresh may be required for tool discovery. CopilotKit test patterns applied without an unnecessary SDK. |

## Verification totals

- Frontend:33 tests passed, TypeScript passed, ESLint passed, production build passed; npm dependency audit clean at installation.
- Backend/database/MCP:47 tests passed,1 live Snowflake test skipped. Ruff passed. One upstream Starlette TestClient deprecation warning does not affect app execution.
- Live Tiger Data:6 repository integration tests passed against isolated test schemas; versioned migrations and pgvector0.8.7 confirmed on the existing service.
- Live Gemini + Tiger:successful preview/save and autocomplete with one selected persisted source. Generation with Gemini3.6 Flash took2.8s in the recorded run; latency varies. Earlier slower model timeouts are documented, not hidden.
- MCP:real Streamable HTTP initialization, discovery of7 tools, panel URL and knowledge forwarding. See ../evidence/mcp-smoke.json.
- UI:../evidence/ui/manifest.json, measurements.json, contact-sheet.png and full-page images. Fixture-backed QA is separate from the live app.

## Release decision

The implemented app and local plugin package are ready for use with Gemini and Tiger Data. Snowflake live verification remains explicitly outstanding. The Codex plugin has been installed and enabled; desktop refresh/new-chat discovery was not driven automatically. Neither is represented by fake success. Startup commands, credentials boundaries and host installation instructions are in ../README.md.
