import { describe, expect, it } from 'vitest';
import { applyEdits, parseEnhancement, validateEdits } from '@/lib/edits';
const request = {
  request_id: 'request-1',
  prompt: 'A😀é中 end',
  prompt_revision: 2,
  cursor_position: 10,
};
describe('UTF-16 atomic edits', () => {
  it('uses original offsets and applies replacements, deletion and insertions from the end', () => {
    expect(
      applyEdits(request.prompt, [
        { start: 1, end: 3, text: '🌍' },
        { start: 6, end: 7, text: '' },
        { start: 10, end: 10, text: '!' },
      ]),
    ).toBe('A🌍é中end!');
  });
  it('preserves combining characters and mixed scripts', () => {
    expect(
      applyEdits('😀é中文', [
        { start: 2, end: 4, text: 'é' },
        { start: 4, end: 6, text: '日本語' },
      ]),
    ).toBe('😀é日本語');
  });
  it.each([
    [{ start: 2, end: 3, text: 'x' }],
    [{ start: -1, end: 0, text: 'x' }],
    [{ start: 0, end: 99, text: 'x' }],
    [{ start: 1.5, end: 3, text: 'x' }],
    [
      { start: 0, end: 3, text: 'x' },
      { start: 2, end: 4, text: 'y' },
    ],
    [
      { start: 0, end: 0, text: 'x' },
      { start: 0, end: 0, text: 'y' },
    ],
  ])('rejects malformed, overlapping or surrogate-splitting ranges: %j', (...edits) => {
    expect(() => validateEdits(request.prompt, edits)).toThrow();
  });
  it('does not mutate inputs', () => {
    const edits = [
      { start: 4, end: 4, text: 'B' },
      { start: 0, end: 0, text: 'A' },
    ];
    applyEdits('text', edits);
    expect(edits[0].start).toBe(4);
  });
});
describe('exact enhancement union', () => {
  const base = { schema_version: 1, request_id: request.request_id, prompt_revision: 2 };
  it('accepts none and a valid unique choice set', () => {
    expect(parseEnhancement({ ...base, type: 'none' }, request).type).toBe('none');
    expect(
      parseEnhancement(
        {
          ...base,
          type: 'multiple_choice',
          question: 'Format?',
          options: [
            { id: 'a', label: 'A', edits: [{ start: 0, end: 0, text: 'A' }] },
            { id: 'b', label: 'B', edits: [{ start: 0, end: 0, text: 'B' }] },
          ],
        },
        request,
      ).type,
    ).toBe('multiple_choice');
  });
  it.each([
    { type: 'none', text: 'forbidden' },
    { type: 'autocomplete', insert_at: 9, text: 'x' },
    { type: 'autocomplete', insert_at: 10, text: '' },
    { type: 'multiple_choice', question: 'Format?', options: [] },
    {
      type: 'multiple_choice',
      question: 'Format?',
      options: [
        { id: 'a', label: 'A', edits: [] },
        { id: 'a', label: 'B', edits: [] },
      ],
    },
  ])('rejects invalid branch %j', (branch) =>
    expect(() => parseEnhancement({ ...base, ...branch }, request)).toThrow(),
  );
  it('rejects an unsupported version or mismatched snapshot', () => {
    expect(() => parseEnhancement({ ...base, type: 'none', schema_version: 2 }, request)).toThrow();
    expect(() => parseEnhancement({ ...base, type: 'none', request_id: 'old' }, request)).toThrow();
    expect(() =>
      parseEnhancement({ ...base, type: 'none', prompt_revision: 1 }, request),
    ).toThrow();
  });
});
