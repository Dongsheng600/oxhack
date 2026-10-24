import React from 'react';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { Refine } from '@/components/refine/refine';
import type { EnhanceRequest } from '@/lib/types';
vi.mock('next/link', () => ({
  default: ({ children, href, ...props }: React.AnchorHTMLAttributes<HTMLAnchorElement>) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}));
vi.mock('sonner', () => ({ toast: { success: vi.fn(), error: vi.fn() } }));
const json = (data: unknown, status = 200) =>
  new Response(JSON.stringify(data), { status, headers: { 'Content-Type': 'application/json' } });
const response = (request: EnhanceRequest, branch: Record<string, unknown>) => ({
  schema_version: 1,
  request_id: request.request_id,
  prompt_revision: request.prompt_revision,
  ...branch,
});
type Handler = (request: EnhanceRequest) => Response | Promise<Response>;
function network(handler: Handler) {
  return vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string, init?: RequestInit) => {
      if (url.endsWith('/enhance')) return handler(JSON.parse(String(init?.body)));
      if (url.includes('/sources')) return json({ sources: [] });
      if (url.endsWith('/outcomes')) return json({ id: 'event' }, 201);
      throw new Error(`Unexpected URL: ${url}`);
    }),
  );
}
function type(value = 'Review this change') {
  const editor = screen.getByRole('textbox', { name: 'Draft prompt' });
  fireEvent.change(editor, {
    target: { value, selectionStart: value.length, selectionEnd: value.length },
  });
  return editor as HTMLTextAreaElement;
}
function enhance() {
  fireEvent.click(screen.getByRole('button', { name: 'Enhance' }));
}
beforeEach(() => {
  vi.stubGlobal('requestAnimationFrame', (callback: FrameRequestCallback) => {
    callback(0);
    return 1;
  });
});
afterEach(() => {
  vi.unstubAllGlobals();
});
describe('refinement journeys through rendered controls', () => {
  it('keeps ghost text out of the draft; accept is atomic and undo/redo restores it', async () => {
    network((request) =>
      json(
        response(request, {
          type: 'autocomplete',
          insert_at: request.prompt.length,
          text: ' with evidence.',
        }),
      ),
    );
    render(<Refine />);
    const editor = type();
    enhance();
    await screen.findByRole('button', { name: /Accept/ });
    expect(editor).toHaveValue('Review this change');
    expect(screen.getByText('with evidence.', { selector: '.ghost' })).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /Accept/ }));
    expect(editor).toHaveValue('Review this change with evidence.');
    editor.setSelectionRange(0, 0);
    fireEvent.select(editor);
    expect(screen.getByRole('status')).toHaveTextContent('Changes applied');
    fireEvent.click(screen.getByRole('button', { name: 'Undo' }));
    expect(editor).toHaveValue('Review this change');
    expect(editor).toHaveFocus();
    fireEvent.keyDown(editor, { key: 'z', ctrlKey: true, shiftKey: true });
    expect(editor).toHaveValue('Review this change with evidence.');
  });
  it('opens a diff without applying and removes copy until confirmation', async () => {
    network((request) =>
      json(
        response(request, {
          type: 'multiple_choice',
          question: 'Which format?',
          options: [
            {
              id: 'list',
              label: 'Findings',
              edits: [
                { start: 0, end: 6, text: 'Audit' },
                { start: request.prompt.length, end: request.prompt.length, text: ' as findings.' },
              ],
            },
            {
              id: 'plan',
              label: 'Plan',
              edits: [
                { start: request.prompt.length, end: request.prompt.length, text: ' as a plan.' },
              ],
            },
          ],
        }),
      ),
    );
    render(<Refine />);
    type();
    enhance();
    await screen.findByRole('radio', { name: 'Findings' });
    fireEvent.click(screen.getByRole('radio', { name: 'Findings' }));
    expect(screen.getAllByText('Not applied').length).toBeGreaterThan(0);
    expect(screen.queryByRole('button', { name: 'Copy prompt' })).not.toBeInTheDocument();
    expect(localStorage.getItem('prompt-enhance.draft')).toBe('Review this change');
    fireEvent.click(screen.getByRole('button', { name: 'Confirm changes' }));
    expect(screen.getByRole('textbox', { name: 'Draft prompt' })).toHaveValue(
      'Audit this change as findings.',
    );
    fireEvent.click(screen.getByRole('button', { name: 'Undo' }));
    expect(screen.getByRole('textbox', { name: 'Draft prompt' })).toHaveValue('Review this change');
  });
  it('declines all without changing whitespace', async () => {
    network((request) =>
      json(
        response(request, {
          type: 'multiple_choice',
          question: 'Which format?',
          options: [
            { id: 'a', label: 'A', edits: [{ start: 0, end: 0, text: 'A' }] },
            { id: 'b', label: 'B', edits: [{ start: 0, end: 0, text: 'B' }] },
          ],
        }),
      ),
    );
    render(<Refine />);
    const editor = type('  Preserve\n this  ');
    enhance();
    await screen.findByRole('button', { name: 'Decline all' });
    fireEvent.click(screen.getByRole('button', { name: 'Decline all' }));
    expect(editor).toHaveValue('  Preserve\n this  ');
  });
  it('distinguishes a healthy none from HTTP failure and preserves the draft on retry', async () => {
    let calls = 0;
    const ids: string[] = [];
    network((request) => {
      ids.push(request.request_id);
      calls++;
      return calls === 1
        ? json(
            { error: { message: 'Gemini timed out', code: 'provider_timeout', retryable: true } },
            503,
          )
        : json(response(request, { type: 'none' }));
    });
    render(<Refine />);
    const editor = type();
    enhance();
    await screen.findByRole('alert');
    expect(screen.getByRole('alert')).toHaveTextContent('Gemini timed out');
    expect(editor).toHaveValue('Review this change');
    fireEvent.click(screen.getByRole('button', { name: 'Retry' }));
    await screen.findByRole('heading', { name: 'No suggestion' });
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    expect(ids[0]).not.toBe(ids[1]);
  });
  it('accepts Tab only when editor focused and ignores IME shortcuts', async () => {
    network((request) =>
      json(
        response(request, {
          type: 'autocomplete',
          insert_at: request.prompt.length,
          text: ' suffix',
        }),
      ),
    );
    render(<Refine />);
    const editor = type();
    enhance();
    await screen.findByRole('button', { name: /Accept/ });
    fireEvent.keyDown(editor, { key: 'Tab', isComposing: true });
    expect(editor).toHaveValue('Review this change');
    fireEvent.keyDown(editor, { key: 'Tab' });
    expect(editor).toHaveValue('Review this change suffix');
  });
});
describe('concurrent request invalidation', () => {
  it('does not revive an old response after cursor away and back', async () => {
    let resolve: (value: Response) => void = () => {};
    let pending: EnhanceRequest | undefined;
    network((request) => {
      pending = request;
      return new Promise<Response>((done) => {
        resolve = done;
      });
    });
    render(<Refine />);
    const editor = type();
    enhance();
    await waitFor(() => expect(pending).toBeDefined());
    editor.setSelectionRange(0, 0);
    fireEvent.select(editor);
    editor.setSelectionRange(editor.value.length, editor.value.length);
    fireEvent.select(editor);
    await act(async () =>
      resolve(
        json(
          response(pending!, {
            type: 'autocomplete',
            insert_at: pending!.prompt.length,
            text: ' STALE',
          }),
        ),
      ),
    );
    expect(screen.queryByText(' STALE')).not.toBeInTheDocument();
    expect(editor).toHaveValue('Review this change');
  });
  it('does not let a stale error overwrite a newer successful request', async () => {
    let reject: (value: Error) => void = () => {};
    let calls = 0;
    network((request) => {
      calls++;
      return calls === 1
        ? new Promise<Response>((_, done) => {
            reject = done;
          })
        : json(response(request, { type: 'none' }));
    });
    render(<Refine />);
    type();
    enhance();
    await waitFor(() => expect(calls).toBe(1));
    type('New draft');
    enhance();
    await screen.findByRole('heading', { name: 'No suggestion' });
    await act(async () => reject(new Error('Old service error')));
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'No suggestion' })).toBeInTheDocument();
  });
  it('invalidates a displayed suggestion immediately on a text change', async () => {
    network((request) =>
      json(
        response(request, {
          type: 'autocomplete',
          insert_at: request.prompt.length,
          text: ' suffix',
        }),
      ),
    );
    render(<Refine />);
    type();
    enhance();
    await screen.findByRole('button', { name: /Accept/ });
    type('Updated prompt');
    expect(screen.queryByRole('button', { name: /Accept/ })).not.toBeInTheDocument();
  });
  it('does not request enhancement during composition and debounces after completion', async () => {
    const requests: EnhanceRequest[] = [];
    network((request) => {
      requests.push(request);
      return json(response(request, { type: 'none' }));
    });
    render(<Refine />);
    const editor = screen.getByRole('textbox', { name: 'Draft prompt' });
    fireEvent.compositionStart(editor);
    type('日本語');
    await new Promise((done) => setTimeout(done, 750));
    expect(requests).toHaveLength(0);
    fireEvent.compositionEnd(editor);
    await waitFor(() => expect(requests).toHaveLength(1), { timeout: 1500 });
    expect(requests[0].prompt).toBe('日本語');
  });
});
