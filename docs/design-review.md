# Prompt Enhance design review

This review translates the brief into a visual inventory and acceptance checks. The UI must follow the current authoritative [`references/design.md`](../references/design.md), which points to [`design.md`](../design.md) as the baseline. Those references were established during this task; they were not present in the original empty checkout.

## Page and state inventory

| Page / tab | Required states and content | Acceptance checks |
| --- | --- | --- |
| Refine | Current draft; autocomplete ghost suffix; multiple-choice question with at least two choices; selected choice diff preview; no suggestion; pending request; service error; stale response. | Ghost text is visually distinct and never appears as committed prompt text before acceptance. Accept inserts only the suffix at the prompt end. Each option previews the result of its edits against the same prompt revision. Apply commits all edits atomically; dismissing all choices leaves the prompt untouched. Any prompt or cursor movement invalidates prior suggestions, and responses with mismatched request ID or revision are ignored. A service failure is visibly distinct from `none`. |
| Knowledge | Knowledge list; empty list; selected item detail; add/import form; validating or generating summary/tags; success; duplicate; validation or service failure. Use plausible entries such as a project skill and a strong example prompt, with source, summary, tags, and update time. | Detail view makes the actual source and summary readable. Add flow shows generated summary/tags before saving and clearly identifies duplicates. Do not imply access controls or multi-user behavior. Knowledge is reference material; any resulting prompt edit still requires the Refine acceptance flow. |
| Activity | API log list/detail and AI-call log list/detail; loading, empty, and failure states. Use realistic request IDs, timestamps, operation/model names, status, latency, token usage when available, retrieval scores, suggestion type, acceptance/decline events, and sanitized errors. | API and AI calls are distinguishable, and details agree with summary rows. Reflect the approved metadata-only policy: omit prompts, retrieved knowledge, model responses, request/response bodies, and credentials. Display the 30-day retention period and ensure expired rows are not presented as available. |
| Settings | Appearance, provider configuration, and the approved logging policy; include validation and save/error states for settings that are actually editable. | Keep credentials backend-side. State clearly that API and AI-call metadata is retained for 30 days; payload logging is disabled. Do not add a payload-logging toggle that contradicts the approved policy. |

Across every tab, include keyboard focus, loading, empty, error, and narrow-screen states where applicable. On mobile, keep prompt text readable and keep accept, dismiss, and navigation actions visible and operable without covering the input. Use meaningful labels and accessible names; avoid decorative subtitles, explanatory card blurbs, and filler helper sentences per the brief.

## Content and interaction traps

- Use a grounded example prompt with an incomplete but plausible request, such as “Summarize the incident report for the on-call handoff”. A useful question can clarify audience or output format; it must not invent project facts or preferences.
- Show both cursor position and prompt revision changes invalidating an in-flight suggestion. Text-only stale handling misses a specified case.
- Multiple-choice edit coordinates refer to one prompt snapshot. Make the preview and resulting prompt demonstrate a safe, atomic application; avoid presenting separate edits as independently applicable.
- Include a decline-all action. It must preserve the full draft byte-for-byte (including spacing) and return focus to the prompt.
- `type: "none"` means the request completed successfully without a useful suggestion; HTTP failure means service error. Never draw both as the same blank or success state.
- A knowledge item can inform a suggestion, but its retrieval is not user consent to change the prompt. Keep source attribution visible when retrieved knowledge contributes.
- Logs can show the approved metadata fields and sanitized errors. Never show full prompts/request bodies, retrieved content, model output, or credentials. API-call, AI-call, and exported outcome-event rows expire after 30 days.
- A mobile mockup should preserve access to the input while a choice or diff is open. The user must be able to inspect the proposed change and dismiss it without accidentally applying it.

## CopilotKit test patterns to reuse after design approval

The examples below come from the primary [`CopilotKit/CopilotKit` repository](https://github.com/CopilotKit/CopilotKit), mainly its current React v2 package. They are testing patterns, not a recommendation to add its SDK. This product has a distinct request/response contract; add a CopilotKit dependency only if an approved integration needs it.

| Pattern | CopilotKit source | How it applies here |
| --- | --- | --- |
| Exercise real user-visible flows with React Testing Library and deterministic fixture agents. Cover typing, Enter, streamed updates, and complete tool lifecycle. | [`CopilotChat.e2e.test.tsx`](https://github.com/CopilotKit/CopilotKit/blob/main/packages/react-core/src/v2/components/chat/__tests__/CopilotChat.e2e.test.tsx) | Test accept/autocomplete, option selection, diff confirmation, and decline through rendered controls. Stub the enhancement API deterministically; assert prompt result and network contract. |
| Assert layout relationships through accessible/test IDs and DOM order, including welcome versus active-chat states and measured input space. | [`CopilotChatView.inputOverlay.test.tsx`](https://github.com/CopilotKit/CopilotKit/blob/main/packages/react-core/src/v2/components/chat/__tests__/CopilotChatView.inputOverlay.test.tsx) | Verify the suggestion surface stays associated with the prompt, does not occlude input, and preserves mobile action order. Prefer observable behavior and stable test IDs over fragile CSS snapshots. |
| Test both failing and healthy connection behavior, asserting an error callback and that the healthy path remains quiet. | [`CopilotChat.onError.test.tsx`](https://github.com/CopilotKit/CopilotKit/blob/main/packages/react-core/src/v2/components/chat/__tests__/CopilotChat.onError.test.tsx) | Pair a service-error case with a successful `type: "none"` case. Assert distinct, accessible UI states and that errors do not erase the draft. |
| Test async state through request mocks and lifecycle transitions; assert calls by URL and method rather than fixed invocation order, and verify teardown. | [`use-threads.test.tsx`](https://github.com/CopilotKit/CopilotKit/blob/main/packages/react-core/src/v2/hooks/__tests__/use-threads.test.tsx) | Assert request ID/revision handling, stale response rejection, log metadata, and cancellation/cleanup without coupling tests to incidental request ordering. |

For this app, add focused component and integration coverage for the discriminated response union (`autocomplete`, `multiple_choice`, `none`), valid half-open UTF-16 ranges, overlapping or out-of-bounds edits, atomic right-to-left application, and stale request/revision rejection. These are brief-specific contracts rather than behavior to inherit from CopilotKit.

## Review status

This is a requirements review, not approval of any mockup. The metadata-only logging policy and 30-day retention have explicit user approval; the design gate remains in force until the complete desktop and mobile mockup set is rendered and reviewed.

## Baseline consistency check

The current `design.md` inventory covers the four requested tabs and the required suggestion, knowledge, and log states. Its revision/cursor invalidation, diff confirmation, decline-all, no-suggestion/error distinction, no invented facts, source attribution, and separate Codex editor/copy path align with the brief. Metadata-only logging with 30-day expiry now matches the user's later explicit decision and supersedes the original brief's unresolved-decision note. The add-source summary/tag preview and undo action are additional workflow detail, not conflicting requirements. No direct requirement conflict was found in the written baseline. The rendered mockups remain to be checked against it.

## Rendered mockup inspection

I inspected the contact sheet and the four requested full-size files: [03-diff-mobile-light.png](../design/mockups/03-diff-mobile-light.png), [08-add-mobile-light.png](../design/mockups/08-add-mobile-light.png), [09-api-desktop-light.png](../design/mockups/09-api-desktop-light.png), and [12-settings-mobile-dark.png](../design/mockups/12-settings-mobile-dark.png). This was a visual inspection of design artifacts only; it does not verify browser interactions, implementation behavior, or the uninspected full-size screens.

| Mockup | Finding | Recommended correction |
| --- | --- | --- |
| `03-diff-mobile-light.png` | Initial review found an enabled “Copy prompt” before confirmation and two redundant explanatory captions. Reinspection shows the Copy action and captions have been removed. The diff is labeled “Not applied,” and the only commit action is “Confirm changes.” | Resolved in the current image: the proposed change remains pending until confirmation, with no competing copy path. |
| `08-add-mobile-light.png` | Initial review found a completed form and summary/tag preview with a disabled-looking “Save source.” Reinspection shows stage `02 / 02`, `Ready`, and an enabled “Save source” action. | Resolved in the current image: the completed preview has a clear ready state and available save action. |
| `09-api-desktop-light.png` | The API activity screen visibly states “Metadata only” and “30-day retention,” lists status and latency, and does not show request bodies or credentials. This matches the approved logging decision. | No change identified in this inspected screen. |
| `12-settings-mobile-dark.png` | Settings states “Metadata only,” “30 days,” and excludes payloads and credentials. “Composer access: Not verified” and “MCP: Planned” communicate the integration boundary without claiming working Codex composer access. | No change identified in this inspected screen. |

Follow-up inspection of the revised [03-diff-mobile-light.png](../design/mockups/03-diff-mobile-light.png) and [08-add-mobile-light.png](../design/mockups/08-add-mobile-light.png) verifies both findings are resolved. The additional [15-import-error-mobile-light.png](../design/mockups/15-import-error-mobile-light.png) shows a clear summary-generation failure, preserves the entered source content, offers Retry, and marks the summary/tag preview unavailable without fabricating generated content. These are design-stage visual checks only.

The contact sheet shows a coherent shared visual system and the numbered inventory across desktop/mobile, theme variants, and narrow panel. At contact-sheet scale it cannot establish text legibility, focus visibility, tap target size, or behavior for every screen; those still need individual inspection and interactive review. The two initial findings are resolved in the revised images. These are design-stage corrections, not evidence of production behavior. Production UI, services, persistence, and integrations remain unimplemented.
