# Prompt Enhance

A working single-user prompt refinement app and local Codex MCP plugin. The complete v1 mockups were approved on 24 October 2026. The app uses Next.js/React, FastAPI/Pydantic, Gemini, and PostgreSQL/pgvector on Tiger Data.

Open the running app at [127.0.0.1:3000](http://127.0.0.1:3000/). It provides optional ghost-text completion, multiple-choice suggestions with a confirmation diff, a persistent knowledge library, API/AI activity, model settings, and light/dark themes. **Copy prompt** transfers the accepted draft to your clipboard for Codex. Native composer interception is not implemented.

## Verified integrations

- **Gemini + Tiger Data:** live preview, transactional save, tag embeddings, retrieval, relevance selection, full-source generation, and correlated activity passed. A real `Review with evidence` source is saved in the hosted library.
- **Codex MCP:** Streamable HTTP initialization, seven-tool discovery, panel link, and backend forwarding passed locally. The portable plugin package is in `plugin/`. The plugin is installed and enabled as `prompt-enhance@prompt-enhance-local`; refresh Codex or open a new chat if it is not yet discoverable.
- **Snowflake:** export, cleanup, training, evaluation, prediction, and cold-start behavior are implemented and contract-tested. It remains disabled because no Snowflake account is available. No trained classifier or live Snowflake result is fabricated.
- **Privacy:** API/AI logs contain metadata only and expire after 30 days. Expired rows are immediately excluded from reads/exports; startup/hourly cleanup drains expired batches. Credentials, prompts, source bodies, and model responses are excluded from logs. Intentionally saved knowledge and the local browser draft are product data, not logs.

Validation: **33 frontend tests and 47 backend/database/MCP tests passed**, plus live Tiger Data and Gemini checks. The one live Snowflake test is skipped. See [acceptance results](docs/acceptance.md), [live evidence](evidence/live-gemini.json), and [visual QA](design-qa.md).

## Install and run

Requirements: Python 3.12+, Node.js 22+, and PostgreSQL with pgvector. Docker is optional for local database development.

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock -e backend -e plugin
cd frontend
npm ci
npm run build
```

Create `.env` from `.env.example` only if it does not already exist. Set `GEMINI_API_KEY` and `DATABASE_URL` there. **This workspace is already configured; do not overwrite its credentials.** `.env` is ignored by Git. Never put credentials in frontend variables or chat messages. Generative role assignments are persisted through Settings; embedding changes require controlled reindexing.

From the repository root, run each command in its own terminal:

```sh
.venv/bin/python scripts/run.py api
.venv/bin/python scripts/run.py web --production
.venv/bin/python scripts/run.py mcp
```

The services listen on loopback at ports 8000 (API), 3000 (editor), and 8001 (MCP). Omit `--production` for Next development mode. The runner loads `.env` as data, never as shell code, and suppresses HTTP access logging that could contain query text. Services must remain running for the local plugin to work. Authentication and public hosting are outside v1.

For local PostgreSQL instead of Tiger Data:

```sh
docker compose up -d db
```

Set `DATABASE_URL` to the local value in `.env.example`. The API applies versioned migrations on startup. [Database operations](docs/database.md) covers retention and reindexing.

## Codex plugin

`plugin/plugin.json`, `plugin/mcp.json`, and `plugin/skills/refine-prompt/SKILL.md` form a portable local plugin. This workspace has a registered marketplace at `.agents/plugins/marketplace.json` and the plugin is already installed. On another machine, run `codex plugin marketplace add .` and `codex plugin add prompt-enhance@prompt-enhance-local` from this repository. Keep the services running, then invoke Prompt Enhance. `open_refinement_panel` returns the editor URL; open it in a Codex browser panel. The tool-only enhancement path preserves the same acceptance rules.

The endpoint is `http://127.0.0.1:8001/mcp`. Tools: `open_refinement_panel`, `enhance_prompt`, `enhancement_sources`, `search_knowledge`, `read_knowledge`, `preview_knowledge`, and `save_knowledge`. See [official packaging guidance](https://developers.openai.com/plugins/build/plugins) for host registration. The package does not assume an undocumented composer API or iframe capability.

## Checks

```sh
cd frontend
npm test
npm run typecheck
npm run lint
npm run build
```

From the repository root, unit/contract tests run without cloud credentials:

```sh
.venv/bin/python -m pytest backend/tests plugin/tests -q
.venv/bin/python -m ruff check backend/app backend/tests plugin scripts/run.py
```

To include real local PostgreSQL tests after starting Docker:

```sh
DATABASE_URL=postgresql://prompt_enhance:prompt_enhance@127.0.0.1:54329/prompt_enhance TEST_DATABASE_URL=postgresql://prompt_enhance:prompt_enhance@127.0.0.1:54329/prompt_enhance .venv/bin/python -m pytest backend/tests plugin/tests -q
```

Provider fixtures exist only in tests, including `backend/tests/qa_server.py` for deterministic browser edge cases in an isolated schema. Production has no mocked-success mode. Coverage includes UTF-16 boundaries, overlapping edits, text/cursor races, confirmation/undo, ingestion rollback/idempotency, metadata redaction, expiry, and classifier cold start.

## Project map

| Path | Purpose |
| --- | --- |
| `frontend/` | Next app, colocated components/styles, interaction tests |
| `backend/app/` | API, orchestration, Gemini, persistence, Snowflake |
| `database/` | Versioned migrations and operations |
| `plugin/` | Portable manifest, MCP bridge, refinement skill |
| `contracts/http.md` | Exact HTTP contracts |
| `design.md` | Approved visual/interaction contract |
| `design/mockups/` | Approved mockup manifest; PNG images kept locally |
| `evidence/` | Sanitized live evidence and visual manifests; PNG images kept locally |

PNG mockups and screenshots are excluded from Git and retained only in the local workspace. The original gallery at `index.html` requires those local images; the production app does not. `design/prototype/` contains design-only fixtures, separate from the real app. [Original brief](docs/original-brief.md), [architecture](docs/architecture.md), and [integration decisions](docs/integrations.md) preserve scope and provenance.
