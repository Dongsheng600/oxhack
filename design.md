# Prompt Enhance — design contract

Version: 1. Status: APPROVED by the user on 2026-10-24. Production implementation authorized.

## Scope and approval

This is a single-user prompt refinement tool for Codex. The user approved the complete v1 mockup set and authorized frontend, backend, database and integration implementation on 2026-10-24. The original mockups remain the visual baseline. The user requested browser-rendered desktop and mobile mockups before any production UI. Approval applies to the complete numbered set in `design/mockups/manifest.json`, not to an individual screen. Material brief or visual changes reopen the gate.

The original `references/design.md` and `references/sources.md` were absent from the empty workspace. The new files record this fact and establish a baseline; they are not recovered source materials. The request overrides a generic three-option ideation workflow: deliver one coherent, complete browser-rendered direction.

## Direction

An editorial workspace for deliberate prompt writing: warm paper, forest-green actions, crisp rules, small numbered navigation, and generous space around the draft. Serif page titles are paired with system sans-serif controls and monospace operational data. No gradient, decorative illustration, oversized marketing hero, card blurbs, page subtitles, or explanatory filler inside the application. Labels, source content, metadata, real questions, and actionable errors are necessary content.

## Tokens

| Token | Light | Dark |
|---|---|---|
| canvas | `#F5F5EF` | `#141B18` |
| panel | `#FFFFFF` | `#1D2722` |
| sidebar | `#ECEEE6` | `#101713` |
| text | `#202B25` | `#EDF2E9` |
| muted text | `#5E6C62` | `#ACB8AF` |
| border | `#D5DBD2` | `#3D4B42` |
| action | `#244D3B` | `#C3E3A0` |
| on-action | `#FFFFFF` | `#17251A` |
| soft action | `#EAF0E4` | `#2C3B2A` |
| added text | `#245136` on `#E8F3DF` | `#D6F0C1` on `#2A432B` |
| removed text | `#863D31` on `#F9E9E4` | `#FFD8CA` on `#543A32` |
| error | `#973B2C` | `#FFC5AF` |
| focus | `#276750` | `#C3E3A0` |

Fonts: system UI sans, Georgia for page titles only, system monospace for IDs, latency, token counts and source text. Title 36/40px desktop, 30/36px mobile; draft 22/34px desktop, 19/30px mobile; body 14/21px; labels 12/18px; mono 12/18px. Spacing scale 4, 8, 12, 16, 24, 32, 40, 48. Control height 44px. Radius 6px controls and 12px panels. One-pixel rules. No decorative shadows.

## Layout

Desktop artboard: 1280 × 900. A 200px navigation rail, 64px top bar, 40px content margin. Refine uses a wide editor and 310px suggestion rail. Knowledge and Activity use structured rows and a detail route. Mobile artboard: 390 × 1000; the rail becomes a 4-item navigation row, content margin 20px, all panels stack. Long content scrolls vertically; no horizontal page overflow. A 560px narrow panel variant demonstrates the Codex companion footprint. Iframe artboards use real layout widths, not a scaled desktop approximation. Images may show a viewport into a longer page; the prototype remains scrollable.

## Pages and states

| ID | Tab / route | Primary state |
|---|---|---|
| 01 | Refine | Autocomplete suffix, explicit Accept / Dismiss |
| 02 | Refine | Multiple-choice question, three options, Decline all |
| 03 | Refine | Selected-option diff, Confirm changes / Back |
| 04 | Refine | No suggestion |
| 05 | Refine | Service error, Retry / Continue writing |
| 06 | Knowledge | Library with type/tag filters |
| 07 | Knowledge | Source detail, summary, tags, content |
| 08 | Knowledge | Add source form and summary/tag preview |
| 09 | Activity | API calls |
| 10 | Activity | AI calls |
| 11 | Activity | Correlated request detail |
| 12 | Settings | Appearance, providers, approved logging policy |
| 13 | Refine | Empty draft |
| 14 | Knowledge | Empty library |
| 15 | Knowledge | Ingestion failure with Retry |

Each inventory item is rendered at desktop and mobile sizes in light mode. Dark mode is rendered for all four primary tabs at both sizes. Narrow Refine is an additional layout check. Loading, stale invalidation, import processing/duplicate, invalid source fields, disabled apply, accepted/declined, and keyboard focus are interaction/acceptance states within these routes, not additional navigation pages. See `docs/acceptance.md` for production acceptance; design simulations do not satisfy it.

## Refine interaction contract

The complete draft remains visible; ghost text appears only at its end and has a labeled suggestion action. It never becomes part of the prompt until accepted. Do not rely on pale text or color alone. A question has at least two options with unique IDs. Selection opens a diff of the same prompt snapshot; confirmation atomically applies edits from the end backwards. Decline all leaves the draft unchanged. All accepted edits can be undone.

Every text mutation increments prompt_revision. Every text or cursor change invalidates pending suggestions; request ID, revision and cursor snapshot must match before display and again before apply. Positions use UTF-16 units, not Python code-point indexes. Reject out-of-range, overlapping and surrogate-splitting edits. A service failure is an error, never a fabricated `none`. Successful empty retrieval may lead to general enhancement. Missing facts become questions, not invented defaults.

Metadata-only activity is visible; prompts, retrieved content, responses and secrets are absent. Sources listed in Knowledge are intentional stored knowledge, not request payload logs. All displayed examples and status values are fixture data, labeled in the review frame outside the application. Actual connection states must be supplied by real health checks after implementation.

## Accessibility and responsive behavior

Native controls, visible labels, 44px targets, visible 2px focus ring, keyboard-accessible tabs. Questions use a radio group; choosing never applies. The editor stays usable while suggestions load. Esc dismisses; Tab only accepts while a suggestion is eligible and the editor has focus, never trapping focus. Mobile has explicit Accept and Confirm buttons. Diff includes Added/Removed labels as well as color. Errors identify the failed operation and offer a recovery action. Reduced-motion preference disables nonessential animation. Default theme follows system; explicit Light/Dark persisted only in the eventual application.

## Integration boundaries

MCP tool integration is documented for Codex; composer interception and native embedded panel availability remain unverified. The baseline is a separate refinement editor with an explicit Copy prompt action. Embedded UI should be capability-detected; no automatic injection or auto-submit is designed. See `docs/integrations.md`.

Production stack remains the user's React/Next.js/TypeScript stack, FastAPI/Pydantic/Python 3.12+, Gemini, Tiger Data PostgreSQL+pgvector and Snowflake. The prototype uses dependency-free HTML/CSS/JS solely for reproducible design capture. Component-specific styles are colocated. CopilotKit test patterns inform the future suite; adding its SDK remains conditional on an approved feature needing it.

## Decisions

- 2026-10-24: User explicitly approved metadata-only API and AI logs with 30-day retention. Full prompt, knowledge payload and response logging is disabled. Credentials are excluded. The approved implementation now enforces this policy; see docs/architecture.md and evidence/live-gemini.json.
- The final Gemini integration requirement is the provisional interpretation of the earlier undefined “Jev” relevance-model name.
- No login, authorization UI, workspace switcher, or multi-user isolation.
- No decorative subtexts or invented project facts in suggestions.

- 2026-10-24: User approved the complete v1 mockup set and requested production implementation with multiple dedicated agents. Earlier GAG/MPST AGENTS.md instructions were revoked.
