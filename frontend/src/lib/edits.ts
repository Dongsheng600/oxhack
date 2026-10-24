import type { Edit, EnhanceResponse, EnhanceRequest } from './types';
const invalid = () => {
  throw new Error('The service returned an invalid suggestion. Retry the request.');
};
export function isBoundary(text: string, index: number) {
  if (index <= 0 || index >= text.length) return true;
  const left = text.charCodeAt(index - 1),
    right = text.charCodeAt(index);
  return !(left >= 0xd800 && left <= 0xdbff && right >= 0xdc00 && right <= 0xdfff);
}
export function validateEdits(prompt: string, edits: Edit[]) {
  if (!Array.isArray(edits) || !edits.length) invalid();
  edits.forEach((edit) => {
    if (
      !edit ||
      Object.keys(edit).some((key) => !['start', 'end', 'text'].includes(key)) ||
      !Number.isInteger(edit.start) ||
      !Number.isInteger(edit.end) ||
      edit.start < 0 ||
      edit.end < edit.start ||
      edit.end > prompt.length ||
      typeof edit.text !== 'string' ||
      !isBoundary(prompt, edit.start) ||
      !isBoundary(prompt, edit.end)
    )
      invalid();
  });
  const sorted = [...edits].sort((a, b) => a.start - b.start || a.end - b.end);
  sorted.forEach((edit, i) => {
    if (i && (sorted[i - 1].end > edit.start || sorted[i - 1].start === edit.start)) invalid();
  });
  return sorted;
}
export function applyEdits(prompt: string, edits: Edit[]) {
  return validateEdits(prompt, edits)
    .reverse()
    .reduce((text, edit) => text.slice(0, edit.start) + edit.text + text.slice(edit.end), prompt);
}
export function parseEnhancement(value: unknown, request: EnhanceRequest): EnhanceResponse {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return invalid();
  const data = value as Record<string, unknown>;
  if (
    data.schema_version !== 1 ||
    data.request_id !== request.request_id ||
    data.prompt_revision !== request.prompt_revision
  )
    return invalid();
  const base = ['schema_version', 'request_id', 'prompt_revision', 'type'];
  const exact = (extra: string[]) => {
    if (Object.keys(data).some((key) => ![...base, ...extra].includes(key))) invalid();
  };
  if (data.type === 'autocomplete') {
    exact(['insert_at', 'text']);
    if (
      data.insert_at !== request.prompt.length ||
      request.cursor_position !== request.prompt.length ||
      typeof data.text !== 'string' ||
      !data.text.length
    )
      invalid();
  } else if (data.type === 'multiple_choice') {
    exact(['question', 'options']);
    if (
      typeof data.question !== 'string' ||
      !data.question.trim() ||
      !Array.isArray(data.options) ||
      data.options.length < 2
    )
      invalid();
    const ids = new Set<string>();
    for (const item of data.options as unknown[]) {
      if (!item || typeof item !== 'object') invalid();
      const option = item as Record<string, unknown>;
      if (
        Object.keys(option).some((key) => !['id', 'label', 'edits'].includes(key)) ||
        typeof option.id !== 'string' ||
        !option.id ||
        ids.has(option.id) ||
        typeof option.label !== 'string' ||
        !option.label.trim()
      )
        invalid();
      ids.add(option.id as string);
      validateEdits(request.prompt, option.edits as Edit[]);
    }
  } else if (data.type === 'none') exact([]);
  else invalid();
  return data as EnhanceResponse;
}
