import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { KnowledgeAdd, KnowledgeDetail, KnowledgeLibrary } from '@/components/knowledge/knowledge';
import { ActivityDetail, ActivityList } from '@/components/activity/activity';
import { Settings } from '@/components/settings/settings';
import type { Activity, Knowledge, Settings as SettingsData } from '@/lib/types';
const { push, theme } = vi.hoisted(() => ({ push: vi.fn(), theme: vi.fn() }));
vi.mock('next/navigation', () => ({ useRouter: () => ({ push }) }));
vi.mock('next/link', () => ({
  default: ({ children, href, ...props }: React.AnchorHTMLAttributes<HTMLAnchorElement>) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}));
vi.mock('next-themes', () => ({ useTheme: () => ({ theme: 'system', setTheme: theme }) }));
vi.mock('sonner', () => ({ toast: { success: vi.fn(), error: vi.fn() } }));
const item: Knowledge = {
  id: 'source-1',
  title: 'Review guide',
  kind: 'skill',
  version: 2,
  summary: 'Use evidence.',
  tags: ['testing'],
  created_at: '2026-10-24T12:00:00Z',
  updated_at: '2026-10-24T12:00:00Z',
  status: 'indexed',
  content: '<script>alert("unsafe")</script>\n# Source',
};
const call: Activity = {
  id: 'span-1',
  request_id: 'request-1',
  timestamp: '2026-10-24T12:00:00Z',
  operation: 'POST /v1/enhance',
  model: null,
  status: 'success',
  status_code: 200,
  latency_ms: 123,
  input_tokens: null,
  output_tokens: null,
  error_code: null,
};
const settings: SettingsData = {
  models: {
    extraction: 'gemini-2.5-flash',
    relevance: 'gemini-2.5-flash',
    generation: 'gemini-2.5-pro',
    summary: 'gemini-2.5-flash',
    embedding: 'gemini-embedding-001',
  },
  embedding_dimensions: 768,
  providers: {
    gemini: { configured: false, status: 'unconfigured' },
    database: { configured: true, status: 'ready' },
    snowflake: { configured: false, status: 'unconfigured' },
  },
  logging: { mode: 'metadata_only', retention_days: 30, payloads: false },
  classifier: { status: 'untrained', labeled_outcomes: 0, model_version: null },
};
const json = (data: unknown, status = 200) =>
  new Response(JSON.stringify(data), { status, headers: { 'Content-Type': 'application/json' } });
function mount(component: React.ReactNode) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 }, mutations: { retry: false } },
  });
  return {
    client,
    ...render(<QueryClientProvider client={client}>{component}</QueryClientProvider>),
  };
}
afterEach(() => vi.unstubAllGlobals());
describe('knowledge API journeys', () => {
  it('searches, filters and paginates through real query URLs', async () => {
    const urls: string[] = [];
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string) => {
        urls.push(url);
        const params = new URL(url, 'http://local').searchParams;
        return json({
          items: params.get('cursor')
            ? [{ ...item, id: 'source-2', title: 'Second guide' }]
            : [item],
          next_cursor: params.get('cursor') ? null : 'page-2',
        });
      }),
    );
    mount(<KnowledgeLibrary />);
    await screen.findByRole('link', { name: /Review guide/ });
    expect(new URL(urls[0], 'http://local').searchParams.has('kind')).toBe(false);
    expect(new URL(urls[0], 'http://local').searchParams.has('q')).toBe(false);
    expect(new URL(urls[0], 'http://local').searchParams.has('tag')).toBe(false);
    fireEvent.click(screen.getByRole('button', { name: 'Load more' }));
    await screen.findByRole('link', { name: /Second guide/ });
    expect(urls.some((url) => url.includes('cursor=page-2'))).toBe(true);
    fireEvent.change(screen.getByRole('combobox', { name: 'Source type' }), {
      target: { value: 'skill' },
    });
    await waitFor(() => expect(urls.some((url) => url.includes('kind=skill'))).toBe(true));
    fireEvent.change(screen.getByRole('searchbox', { name: 'Search knowledge' }), {
      target: { value: 'evidence' },
    });
    await waitFor(() => expect(urls.some((url) => url.includes('q=evidence'))).toBe(true));
  });
  it('renders persisted source as text with summary, tags and version', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => json(item)),
    );
    mount(<KnowledgeDetail id={item.id} />);
    await screen.findByRole('heading', { name: 'Review guide' });
    expect(screen.getByText(item.content!, { normalizer: (value) => value })).toBeInTheDocument();
    expect(document.querySelector('script')).toBeNull();
    expect(screen.getByText('Use evidence.')).toBeInTheDocument();
    expect(screen.getByText('testing')).toBeInTheDocument();
    expect(screen.getByText('2')).toBeInTheDocument();
  });
  it('generates preview, invalidates after input edits, and preserves save idempotency on retry', async () => {
    const saves: unknown[] = [];
    let generation = 0;
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string, init: RequestInit) => {
        if (url.endsWith('/preview')) {
          generation++;
          return json({
            preview_id: `preview-${generation}`,
            title: item.title,
            kind: item.kind,
            summary: item.summary,
            tags: item.tags,
            expires_at: '2026-10-24T13:00:00Z',
          });
        }
        const body = JSON.parse(String(init.body));
        saves.push(body);
        return saves.length === 1
          ? json(
              {
                error: { message: 'Save timed out', code: 'database_unavailable', retryable: true },
              },
              503,
            )
          : json(item, 201);
      }),
    );
    mount(<KnowledgeAdd />);
    fireEvent.change(screen.getByRole('textbox', { name: 'Title' }), {
      target: { value: item.title },
    });
    fireEvent.change(screen.getByRole('textbox', { name: 'Content' }), {
      target: { value: item.content },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Generate summary' }));
    await screen.findByRole('button', { name: 'Save source' });
    fireEvent.change(screen.getByRole('textbox', { name: 'Title' }), {
      target: { value: 'Updated title' },
    });
    expect(screen.queryByRole('button', { name: 'Save source' })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Generate summary' }));
    await screen.findByRole('button', { name: 'Save source' });
    fireEvent.click(screen.getByRole('button', { name: 'Save source' }));
    await screen.findByRole('alert');
    expect(screen.getByRole('textbox', { name: 'Content' })).toHaveValue(item.content);
    fireEvent.click(screen.getByRole('button', { name: 'Retry save' }));
    await waitFor(() => expect(push).toHaveBeenCalledWith('/knowledge/source-1'));
    expect(saves[0]).toEqual(saves[1]);
    expect(saves[0]).toMatchObject({ preview_id: 'preview-2' });
  });
  it('does not fabricate a preview or save action after provider failure', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () =>
        json(
          {
            error: { message: 'Gemini unavailable', code: 'provider_unavailable', retryable: true },
          },
          503,
        ),
      ),
    );
    mount(<KnowledgeAdd />);
    fireEvent.change(screen.getByRole('textbox', { name: 'Title' }), {
      target: { value: 'Guide' },
    });
    fireEvent.change(screen.getByRole('textbox', { name: 'Content' }), {
      target: { value: 'Evidence' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Generate summary' }));
    await screen.findByRole('alert');
    expect(screen.queryByRole('button', { name: 'Save source' })).not.toBeInTheDocument();
    expect(screen.getByRole('textbox', { name: 'Content' })).toHaveValue('Evidence');
    expect(screen.getByRole('button', { name: 'Retry' })).toBeEnabled();
  });
});
describe('activity and settings API journeys', () => {
  it('keeps status filter while switching API / AI tabs', async () => {
    const urls: string[] = [];
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string) => {
        urls.push(url);
        return json({
          items: [{ ...call, model: url.includes('/ai?') ? 'gemini-2.5-flash' : null }],
          next_cursor: null,
        });
      }),
    );
    mount(<ActivityList />);
    await screen.findByRole('link', { name: /POST \/v1\/enhance/ });
    fireEvent.change(screen.getByRole('combobox', { name: 'Status filter' }), {
      target: { value: 'error' },
    });
    fireEvent.click(screen.getByRole('tab', { name: 'AI calls' }));
    await screen.findByText('gemini-2.5-flash');
    expect(urls.some((url) => url.includes('/activity/ai?status=error'))).toBe(true);
    expect(screen.getByRole('combobox', { name: 'Status filter' })).toHaveValue('error');
    expect(screen.getByText('Payload logging off')).toBeInTheDocument();
  });
  it('loads correlated call and source metadata without payloads', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () =>
        json({
          request_id: 'request-1',
          api_calls: [call],
          ai_calls: [
            {
              ...call,
              id: 'ai-span',
              operation: 'generation',
              model: 'gemini-2.5-pro',
              status_code: null,
              input_tokens: 55,
              output_tokens: null,
            },
          ],
          sources: [item],
          expires_at: '2026-11-23T12:00:00Z',
        }),
      ),
    );
    mount(<ActivityDetail id="request-1" />);
    await screen.findByText('generation');
    expect(screen.getByText('gemini-2.5-pro')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Review guide v2' })).toHaveAttribute(
      'href',
      '/knowledge/source-1',
    );
    expect(screen.queryByText(item.content!)).not.toBeInTheDocument();
    expect(screen.getByText('Disabled')).toBeInTheDocument();
  });
  it('shows truthful provider/logging state and persists edited models through PATCH', async () => {
    let stored = settings;
    const writes: unknown[] = [];
    vi.stubGlobal(
      'fetch',
      vi.fn(async (_url: string, init: RequestInit) => {
        if (init?.method === 'PATCH') {
          const body = JSON.parse(String(init.body));
          writes.push(body);
          stored = { ...stored, models: { ...stored.models, ...body.models } };
        }
        return json(stored);
      }),
    );
    const { unmount } = mount(<Settings />);
    await screen.findByText('Tiger Data');
    expect(screen.getAllByText('Not configured')).toHaveLength(2);
    expect(screen.getByText('ready')).toBeInTheDocument();
    expect(screen.getByText('Metadata only')).toBeInTheDocument();
    expect(screen.getByText('30 days')).toBeInTheDocument();
    fireEvent.change(screen.getByRole('textbox', { name: 'generation' }), {
      target: { value: 'gemini-2.5-flash' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Save models' }));
    await waitFor(() => expect(writes).toHaveLength(1));
    expect(writes[0]).toMatchObject({ models: { generation: 'gemini-2.5-flash' } });
    unmount();
    mount(<Settings />);
    await waitFor(() =>
      expect(screen.getByRole('textbox', { name: 'generation' })).toHaveValue('gemini-2.5-flash'),
    );
    fireEvent.change(screen.getByRole('combobox', { name: 'Theme' }), {
      target: { value: 'dark' },
    });
    expect(theme).toHaveBeenCalledWith('dark');
    expect(screen.queryByRole('textbox', { name: 'Embedding' })).not.toBeInTheDocument();
  });
});
