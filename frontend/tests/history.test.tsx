import { act, renderHook, waitFor } from '@testing-library/react';
import { expect, it, vi } from 'vitest';
import { useRefinement } from '@/components/refine/use-refinement';
it('undo and redo preserve the programmatic acceptance in the history stack', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string, init: RequestInit) => {
      const request = JSON.parse(String(init?.body || '{}'));
      return new Response(
        JSON.stringify(
          url.endsWith('/enhance')
            ? {
                schema_version: 1,
                request_id: request.request_id,
                prompt_revision: request.prompt_revision,
                type: 'autocomplete',
                insert_at: request.prompt.length,
                text: ' suffix',
              }
            : url.endsWith('/sources')
              ? { sources: [] }
              : { id: 'event' },
        ),
        { status: 200 },
      );
    }),
  );
  const { result } = renderHook(() => useRefinement());
  act(() => result.current.change('Original', 8));
  await act(async () => result.current.enhance());
  await waitFor(() => expect(result.current.result?.type).toBe('autocomplete'));
  act(() => result.current.accept());
  expect(result.current.snapshot.prompt).toBe('Original suffix');
  act(() => result.current.undo());
  expect(result.current.snapshot.prompt).toBe('Original');
  act(() => result.current.redo());
  expect(result.current.snapshot.prompt).toBe('Original suffix');
  vi.unstubAllGlobals();
});
