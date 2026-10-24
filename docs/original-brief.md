# Prompt Enhance

We are going to build a prompt-enhanced plugin for Codex. This project consists of three parts: frontend, backend, and database. Use multiple dedicated and specific agents with a main orchestrator for this. Spawn subagents using other models to speed up the implementation. Create a git repo for this.

## Usage scope and logging

This is a single-user application. Login authentication, knowledge access controls, and multi-user or workspace isolation are out of scope.

Retain logs for both AI calls and API calls. As a proposed default, record request IDs, timestamps, operation or model names, status, latency, token usage when available, and sanitized error details. Keep model credentials on the backend and exclude secrets from logs. Whether to log full prompts, retrieved knowledge, and model responses, and how long to retain logs, must be decided explicitly before implementing payload logging and retention.

Retrieved knowledge, including SKILL files and example prompts, is reference data for generating suggestions. Any proposed prompt change follows the existing user acceptance flow.

## How to enhance

When the user is inputting their prompts, it will give auto-complete or ask questions.

An auto-complete will show as the ghost text after the user's input, similar to what GitHub Copilot's autocomplete is doing.

A question will be a multiple-choice, where the user can choose one of the options and apply its diff to the prompt. Or the user can decline all of the options and continue writing their prompt.

### Enhancement API response

Return one JSON object using a discriminated `type` field. Positions are UTF-16 code units and use the half-open range `[start, end)`; `start === end` means insertion, and an empty `text` means deletion.

```ts
type Edit = {
  start: number;
  end: number;
  text: string;
};

type EnhanceResponse = {
  schema_version: 1;
  request_id: string;
  prompt_revision: number;
} & (
  | {
      type: "autocomplete";
      insert_at: number;
      text: string;
    }
  | {
      type: "multiple_choice";
      question: string;
      options: Array<{
        id: string;
        label: string;
        edits: Edit[];
      }>;
    }
  | {
      type: "none";
    }
);
```

Autocomplete example:

```json
{
  "schema_version": 1,
  "request_id": "req_123",
  "prompt_revision": 7,
  "type": "autocomplete",
  "insert_at": 10,
  "text": " with examples"
}
```

Multiple-choice example:

```json
{
  "schema_version": 1,
  "request_id": "req_124",
  "prompt_revision": 7,
  "type": "multiple_choice",
  "question": "Which output language should be used?",
  "options": [
    {
      "id": "zh",
      "label": "Chinese",
      "edits": [{"start": 10, "end": 10, "text": "\nPlease respond in Chinese."}]
    },
    {
      "id": "en",
      "label": "English",
      "edits": [{"start": 10, "end": 10, "text": "\nPlease respond in English."}]
    }
  ]
}
```

The request includes `request_id`, the complete prompt, `prompt_revision`, and the cursor position. The client increments `prompt_revision` whenever the prompt changes and accepts a response only when its request ID and revision still match the latest input. Any text or cursor change invalidates older suggestions.

For autocomplete, `insert_at` must equal the current prompt length and `text` must contain only the ghost-text suffix; the text is not applied until the user accepts it. For multiple-choice, each question has at least two options, option IDs are unique within the question, and every option contains at least one edit. All edits are relative to the same prompt snapshot, must have valid bounds, and must not overlap. The client applies selected edits atomically from the end of the prompt toward the beginning and previews the resulting diff before confirmation. Declining all options leaves the prompt unchanged.

Return `type: "none"` when no suggestion is worth displaying. Report service failures with an HTTP error response rather than `none`.

## Frontend

https://github.com/copilotkit/copilotkit

The frontend will be a plugin in openAI's codex that provides a separate panel to refine the prompt, and if possible, better override the input textbox of the codex app. Based on the backend functions, determine how can the frontend be optimized for it. Create a design.md and reference strict consistency to it. Never interpolate user text into shell code. Read [design.md](references/design.md) and the design section of [sources.md](references/sources.md). Establish a distinctive coherent direction, precise tokens, realistic content, and rendered image mockups for every inventoried page/tab on desktop and mobile. Browser-rendered prototypes are preferred for reproducible geometry and typography. Prototypes remain design artifacts; they do not authorize production implementation.  Show a contact sheet and individually viewable images. Apply revisions consistently. End the turn awaiting explicit approval of the complete current mockup set. Do not build production UI yet. Material brief changes return to its approval gate; material visual changes after approval return to this gate.
No decorative subtexts: exclude page subtitles, card blurbs, filler helper sentences, and explanatory captions inside the UI. Keep necessary labels, real product data, accessible names, and actionable validation/errors. Resolve a PRD conflict before removing required content.

After approval:
Apply CopilotKit's test patterns to this app; add its SDK only if approved features need it. Implement real behavior, persistence, and integrations. Static facades, mocked success, and decorative controls cannot satisfy acceptance. Give workers non-overlapping file ownership; tell them they share the checkout and must accommodate others' edits. Supply the approved brief and only relevant designs, source files, and checks. The orchestrator owns integration and final evidence.

Repeat run → inspect failures → fix causes → rerun affected checks and regressions until agreed acceptance and fidelity checks pass. Cover every page/tab, critical journey, and interactive component family.

## Backend

The backend will provide an API to the frontend to get either the auto-complete or the question and options to be shown to the user. The frontend request with the prompts they have input, then we:
1. Based on the input, find tags(this should be done by a small and quick LLM) that may be related to this input.
2. Using the tags from the database, retrieve knowledge and their corresponding summary (like SKILLs or good prompts).
3. With a Jev model, for each knowledge retrieved, review the summary together with the user input to decide whether we really need it or not.
4. Then, with filtered knowledge and the user's input, we generate the autocomplete or questions to ask and return them to users. If retrieval completes successfully with no candidates, or filtering completes successfully and excludes all candidates, allow general enhancement based only on the user's input.

General enhancement may suggest clearer goals, constraints, and output formats. It must not invent project facts, knowledge sources, or user preferences; missing information must be clarified through multiple-choice questions rather than assumed. Return `type: "none"` when no suggestion is worth displaying.

## Database

The database stores all of the knowledge; it consists of two parts:
1. A vector database for tags(pgvector)
2. A database for knowledge (skills.md or deterministic graphs with agent prompting in the loop)

A tag can apply to multiple knowledges, and a knowledge can have multiple tags.
For each knowledge, there should also be a corresponding summary to summarize what it includes. This would be useful for the classifier when we are adding the tags.
When we are adding knowledge to the database, we should generate a summary and a few tags for it. We should add the tag to the vector database if it is not, and link the tags to the knowledge. We should insert the new knowledge, together with a summary to the knowledge database.

When we retrive knowledges from the database, we will provide the tags, then we check the tags stored in the vector database that match them (use nearest neighbour?), and then find their corresponding knowledge.

## Tech Stack

### Code Cleanliness

Don't put too many codes in one file; split codes into files appropriately and reuse code if possible. Write clean code.

For the frontend, put the style together with the components. Don't put all styles in one file.

### Frontend

- React + NextJS
- TypeScript
- Components: shadcn/ui
- Styling: Tailwind CSS
- Theme / Dark Mode: next-themes + shadcn/ui CSS variables
- Query: TanstackQuery
- Icons: Lucide-react
- Linter: ESLint
- Formatter: Prettier
- Hooks: mantine/hooks
- Helper Functions: estoolkit
- Notification: Sonner
- Virtualisation: TanStack Virtual
- Other
  - Animation: Motion
  - Resizable Panel: react-resizable-panels

### Backend

- Python 3.12+ with type annotations
- FastAPI
- Pydantic
- Tiger Data for the database

# Specifc integrations

(https://www.mlh.com/events/oxhack-26/prizes)

Gemini API: Extract tags and task features, embed knowledge, judge relevance, and generate your structured JSON response. Structured outputs, embeddings.
Tiger Data: Store knowledge, summaries, tag relationships, vectors, and timestamped outcome events together in PostgreSQL. You can keep both database parts in one service. Unified database approach.
Snow Flake: Train and evaluate the outcome classifier from structured features such as task type, missing constraints, retrieval scores, and observed results. Its classification function requires derived features rather than raw prompt paragraphs.
