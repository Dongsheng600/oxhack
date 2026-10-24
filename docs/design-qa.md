# Design verification — v1

Date: 24 October 2026. Scope: browser-rendered design artifacts only. The complete set was approved by the user on 24 October 2026. Production implementation QA is recorded in ../design-qa.md.

## Evidence

- 15 screen/state compositions, each at 1280px desktop and 390px mobile: 30 screenshots.
- Four primary tabs in dark mode at desktop and mobile widths: 8 screenshots.
- One 560px companion-panel composition: 1 screenshot.
- Total: **39 individually viewable full-page PNGs**, a complete contact sheet and four-tab overview. `design/mockups/manifest.json` records each viewport, actual image dimensions and SHA-256 hash.
- Every screenshot width matches its declared viewport. Full-page images include vertically scrolling content; mobile content is not cropped to one viewport. No horizontal page overflow was found in the captured layouts.
- The complete contact sheet was visually inspected. Full-size inspection included desktop Refine, mobile question, mobile diff, mobile add-source, API activity and dark Settings. A second agent independently reviewed the contact sheet and critical full-size compositions.

## Review repairs

1. Removed Copy prompt from pending diff preview so that confirmation is the only path to applying the proposed edit. Copy remains available for the draft outside the preview.
2. Removed redundant diff helper captions while keeping the original/proposed distinction, Added marker and Not applied status.
3. Made the valid add-source preview explicitly stage 02/02 with Ready status and an enabled Save source action. The ingestion-error state now shows no fabricated summary or tags; it preserves input and offers Retry.
4. Raised back-link hit targets to 44px, corrected the timeout fixture latency, used revision 00 for an empty draft, and corrected the 30-day expiry display across the BST/GMT transition.
5. Kept the exact enhancement response union intact; added a separate provenance endpoint for the source links displayed in Refine.

Affected screenshots were rendered again, then contact sheets and hashes were rebuilt.

## Prototype interaction checks

Eight checks passed through the Codex in-app browser. Recorded results are in `design/mockups/interaction-checks.json`:

- Selecting Inline comments stages its corresponding diff; Copy prompt is absent.
- Confirmation applies the staged option and increments revision.
- Undo restores the original prompt and advances revision.
- Decline all preserves both the prompt and its revision.
- Autocomplete acceptance appends only the visible suffix.
- Knowledge search filters the fixture rows.
- Activity status filtering isolates the error fixture.
- Theme selection changes the rendered theme.

JavaScript syntax checks passed for the prototype modules. The renderer split was checked against its earlier source with 126 exact HTML comparisons before subsequent review corrections; affected interactions and screenshots were rechecked after those corrections.

## Limits

These checks do not establish production acceptance. The prototype uses local fixtures, has no persistence, no real asynchronous enhancement pipeline, no real structured-output validation, no database, no retention cleanup, no provider calls, and no installed Codex plugin. It is not a production implementation of stale-request handling or a complete editable ghost-text control. Knowledge and activity detail links use representative fixture details. Save and retry demonstrate design states rather than successful external operations.

Full screen-reader, IME, keyboard-navigation, focus-restoration, contrast, race-condition, UTF-16, edit-overlap, deployment, integration and end-to-end testing remains specified in `docs/acceptance.md` for the implementation phase. Do not report those checks as passed. Screenshots and fixture interactions are design evidence only.
