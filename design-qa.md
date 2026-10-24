# Prompt Enhance implementation QA

Date: 24 October 2026. The complete v1 design set was explicitly approved before production implementation.

PNG evidence referenced below is retained in the local workspace and excluded from Git. The committed manifests and measurements describe the completed visual checks.

## Visual truth and evidence

- Source visual truth: `design.md` and `design/mockups/manifest.json` (39 approved images).
- Implementation: `evidence/ui/manifest.json`, `evidence/ui/contact-sheet.png`, and individual full-page screenshots in `evidence/ui/`.
- Production evidence: `evidence/ui/live-app-desktop-light.png` and `live-app-mobile-light.png`, rendered from the running Gemini/Tiger Data app. The mobile capture includes the final wordmark spacing repair.
- Deterministic state coverage uses the production frontend with `backend/tests/qa_server.py`, a test-only injected provider and an isolated PostgreSQL schema. It is not a production mock switch. Live integration evidence is recorded separately in `evidence/live-gemini.json`.

## Viewport and normalization

Source and implementation widths are 1280 CSS pixels (desktop), 390 (mobile), and 560 (companion panel). Viewport heights are 900/1000/1000 respectively. Screenshots are full-page, so their pixel heights vary with real content. Every source/implementation image's pixel dimensions are in its manifest. Captures were normalized from browser-returned bytes to actual RGB PNG; no scale was used during browser rendering. At capture, screenshot width matched CSS viewport width (1:1 density normalization). `evidence/ui/measurements.json` records DOM width, height, theme and scroll width; no captured page had horizontal overflow.

## Compared states

Autocomplete, multiple choice, staged diff, none, service failure, empty draft, knowledge list, source detail, add-preview-ready, filtered empty library, ingestion failure, API activity, AI activity, request detail, and Settings were captured at desktop/mobile. Four primary tabs were captured in dark mode at both widths, plus the 560px editor. The filtered-empty capture exercises the same empty-result component; the unfiltered empty store is additionally covered by component tests.

Full-view comparison evidence includes `autocomplete-comparison.png`, `diff-comparison.png`, `knowledge-comparison.png`, `add-comparison.png`, `api-comparison.png`, and `settings-comparison.png` in `evidence/ui/`. Comparisons use the same CSS scale and omit only the source's 28px design-review banner. The review-gallery link is also intentionally absent in production. Source and implementation content differ where the real data, request IDs, counts, timestamps, suggestions and source summaries differ. Forty loaded activity rows naturally produce longer pages than the five-row design fixture.

The complete contact sheet and full-size desktop Refine/Knowledge/Settings comparisons were inspected. Focused regions were inspected at full size through mobile diff, add-preview-ready, and final production mobile captures: confirm/cancel controls, source Save action, ghost text, focus indication, navigation, and wordmark. Additional image crops were unnecessary because these full-width mobile images expose the control regions clearly.

## Findings and repair history

| Priority | Finding | Repair and post-fix evidence |
| --- | --- | --- |
| P1 | A stale DOM selection event could overwrite accepted autocomplete/undo text. | Selection updates now read the current model prompt, and focus is restored after commit. Browser Tab acceptance advanced revision once and inserted the suffix; Undo restored original text. React regression tests pass. |
| P1 | An empty source-type query value caused API422 on the default Knowledge list. | Empty optional filters are omitted. Real API-backed list/filter/detail/ingestion browser journeys pass; dedicated regression verifies omitted parameters. |
| P2 | Cursor-only selection could remove the post-accept Undo notice. | Cursor changes preserve the notice; browser verified Tab → visible Undo → original prompt restored. |
| P3 | Mobile wordmark rendered PromptEnhance without a space. | Added a literal inter-word space; `live-app-mobile-light.png` shows Prompt Enhance. The prior 39-state captures retain the pre-polish wordmark only. |

No actionable P0/P1/P2 visual or interaction findings remain. The model-role controls extend the existing Settings panel pattern to implement the required editable model settings; they sit below the approved logging panel without changing the primary composition.

## Interaction and console checks

Browser checks covered typing/clearing, autocomplete acceptance with Tab, undo, dismiss, choice/diff/back/confirm, absent Copy during preview, exact clipboard handoff, decline preserving text, none/error distinction, preserved-input failure recovery, search/type filtering, source preview/save/reload, ingestion failure without fabricated tags, API/AI tab switching, status filtering, pagination, correlated request detail, invalid model rejection, model save/reload, and theme persistence. Automated tests additionally cover UTF-16, IME, overlapping edits, stale response/cursor races, and cancellation.

The isolated production-build QA tab returned no warning/error console records. The earlier development tab retained one historical Next/React script-tag warning from before the production server was started; it was not reproduced in the production-build QA tab. No provider credentials or payload logs are included in screenshots or reports.

## Limits

Native Codex composer interception is not implemented. The separate editor and MCP plugin are installed and usable; a Codex refresh/new chat may be needed to discover newly installed tools. Snowflake live training remains deferred because the user has no account. Dedicated screen-reader testing was not performed; keyboard behavior, accessible names and focus were checked in browser and component tests.

final result: passed
