'use client';
import { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useDebouncedValue } from '@mantine/hooks';
import { uniq } from 'es-toolkit';
import { ArrowUpRight, Plus } from 'lucide-react';
import { toast } from 'sonner';
import { api, post, errorMessage, uid } from '@/lib/api';
import type { Kind, Knowledge, Page, Preview } from '@/lib/types';
import { Button, ErrorState, Footer, Heading, Loading, Panel, Pill, Tags } from '@/components/ui';
import './knowledge.css';
const date = (value: string) =>
  new Date(value).toLocaleDateString(undefined, { day: 'numeric', month: 'short' });
export function KnowledgeLibrary() {
  const [search, setSearch] = useState(''),
    [kind, setKind] = useState(''),
    [tag, setTag] = useState('');
  const [q] = useDebouncedValue(search, 250);
  const query = useInfiniteQuery({
    queryKey: ['knowledge', q, kind, tag],
    initialPageParam: '',
    queryFn: ({ pageParam, signal }) =>
      api<Page<Knowledge>>(
        `/knowledge?${new URLSearchParams({ limit: '30', ...(q ? { q } : {}), ...(kind ? { kind } : {}), ...(tag ? { tag } : {}), ...(pageParam ? { cursor: pageParam } : {}) })}`,
        { signal },
      ),
    getNextPageParam: (last) => last.next_cursor || undefined,
  });
  const items = query.data?.pages.flatMap((page) => page.items) || [],
    tags = uniq(items.flatMap((item) => item.tags));
  return (
    <>
      <Heading
        action={
          <Link className="button-link primary" href="/knowledge/new">
            <Plus className="icon" /> Add source
          </Link>
        }
      >
        Knowledge
      </Heading>
      <div className="toolbar">
        <label className="sr-only" htmlFor="search">
          Search knowledge
        </label>
        <input
          className="search-field"
          id="search"
          type="search"
          placeholder="Search knowledge"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
        />
        <div className="filter-group">
          <label className="sr-only" htmlFor="kind">
            Source type
          </label>
          <select id="kind" value={kind} onChange={(event) => setKind(event.target.value)}>
            <option value="">All types</option>
            <option value="skill">Skill</option>
            <option value="prompt">Prompt</option>
            <option value="graph">Graph</option>
          </select>
          <label className="sr-only" htmlFor="tag">
            Tag
          </label>
          <input
            id="tag"
            aria-label="Tag"
            className="tag-filter"
            list="known-tags"
            placeholder="All tags"
            value={tag}
            onChange={(event) => setTag(event.target.value)}
          />
          <datalist id="known-tags">
            {tags.map((value) => (
              <option key={value} value={value} />
            ))}
          </datalist>
        </div>
      </div>
      <Panel>
        {query.isPending ? (
          <Loading />
        ) : query.isError && !query.data ? (
          <ErrorState message={errorMessage(query.error)} retry={() => void query.refetch()} />
        ) : items.length ? (
          <>
            <div className="list-head">
              <span>Source</span>
              <span>Type</span>
              <span>Updated</span>
              <span />
            </div>
            {items.map((item) => (
              <Link
                className="knowledge-row"
                href={`/knowledge/${encodeURIComponent(item.id)}`}
                key={item.id}
              >
                <div>
                  <span className="knowledge-title">{item.title}</span>
                  <Tags tags={item.tags} />
                </div>
                <span className="kind">{item.kind}</span>
                <span className="updated">{date(item.updated_at)}</span>
                <ArrowUpRight className="icon arrow" />
              </Link>
            ))}
            <div className="list-foot">
              <span>
                {items.length} sources · {tags.length} tags
              </span>
              <span>{query.hasNextPage ? 'More available' : 'End of results'}</span>
            </div>
            {query.hasNextPage && (
              <div className="pagination">
                <Button
                  disabled={query.isFetchingNextPage}
                  onClick={() => void query.fetchNextPage()}
                >
                  {query.isFetchingNextPage ? 'Loading…' : 'Load more'}
                </Button>
              </div>
            )}
            {query.isFetchNextPageError && (
              <ErrorState
                message={errorMessage(query.error)}
                retry={() => void query.fetchNextPage()}
              />
            )}
          </>
        ) : (
          <div className="empty-state">
            <h2>{q || kind || tag ? 'No matching sources' : 'No sources yet'}</h2>
            <Link className="button-link primary" href="/knowledge/new">
              Add source
            </Link>
          </div>
        )}
      </Panel>
      <Footer left="TIGER DATA · POSTGRESQL" right={`${items.length} sources loaded`} />
    </>
  );
}
export function KnowledgeDetail({ id }: { id: string }) {
  const query = useQuery({
    queryKey: ['knowledge-detail', id],
    queryFn: ({ signal }) => api<Knowledge>(`/knowledge/${encodeURIComponent(id)}`, { signal }),
  });
  const item = query.data;
  return (
    <>
      <Link className="breadcrumb-back" href="/knowledge">
        ← Knowledge
      </Link>
      {query.isPending ? (
        <Loading />
      ) : query.isError ? (
        <ErrorState message={errorMessage(query.error)} retry={() => void query.refetch()} />
      ) : (
        item && (
          <>
            <Heading
              action={
                <Pill green={item.status === 'indexed' || item.status === 'ready'}>
                  {item.status}
                </Pill>
              }
            >
              {item.title}
            </Heading>
            <div className="detail-grid">
              <Panel title="Source" meta={<span className="count">{item.kind}</span>}>
                <pre className="source-content">{item.content}</pre>
              </Panel>
              <div className="stack summary-panel">
                <Panel title="Summary">
                  <div className="panel-body">
                    <p className="summary-body">{item.summary}</p>
                    <hr className="rule" />
                    <Tags tags={item.tags} />
                  </div>
                </Panel>
                <Panel>
                  <div className="panel-body facts">
                    <div className="fact">
                      <span>Type</span>
                      <span>{item.kind}</span>
                    </div>
                    <div className="fact">
                      <span>Updated</span>
                      <span>{date(item.updated_at)}</span>
                    </div>
                    <div className="fact">
                      <span>Version</span>
                      <span className="mono">{item.version}</span>
                    </div>
                    <div className="fact">
                      <span>Status</span>
                      <span>{item.status}</span>
                    </div>
                  </div>
                </Panel>
              </div>
            </div>
          </>
        )
      )}
    </>
  );
}
export function KnowledgeAdd() {
  const router = useRouter(),
    client = useQueryClient();
  const [title, setTitle] = useState(''),
    [kind, setKind] = useState<Kind>('prompt'),
    [content, setContent] = useState(''),
    [preview, setPreview] = useState<Preview | null>(null),
    [saveKey, setSaveKey] = useState(() => uid());
  const generate = useMutation({
    mutationFn: () => post<Preview>('/knowledge/preview', { title: title.trim(), kind, content }),
    onSuccess: (value) => {
      setPreview(value);
      setSaveKey(uid());
    },
  });
  const save = useMutation({
    mutationFn: () =>
      post<Knowledge>('/knowledge', { preview_id: preview?.preview_id, idempotency_key: saveKey }),
    onSuccess: async (item) => {
      await client.invalidateQueries({ queryKey: ['knowledge'] });
      toast.success('Source saved');
      router.push(`/knowledge/${encodeURIComponent(item.id)}`);
    },
  });
  const invalidate = () => {
    setPreview(null);
    generate.reset();
    save.reset();
  };
  const busy = generate.isPending || save.isPending;
  return (
    <>
      <Link className="breadcrumb-back" href="/knowledge">
        ← Knowledge
      </Link>
      <Heading
        action={
          <Pill error={generate.isError || save.isError}>
            {busy ? 'Processing' : generate.isError || save.isError ? 'Import failed' : 'Unsaved'}
          </Pill>
        }
      >
        Add knowledge
      </Heading>
      <div className="form-grid">
        <Panel
          title="Source details"
          meta={<span className="count">{preview ? '02' : '01'} / 02</span>}
        >
          <form
            className="panel-body"
            onSubmit={(event) => {
              event.preventDefault();
              setPreview(null);
              save.reset();
              generate.mutate();
            }}
          >
            {(generate.isError || save.isError) && (
              <div className="import-error" role="alert">
                <strong>
                  {generate.isError ? 'Summary generation failed' : 'Source save failed'}
                </strong>
                {errorMessage(generate.error || save.error)}
              </div>
            )}
            <div className="field">
              <label htmlFor="source-title">Title</label>
              <input
                id="source-title"
                required
                maxLength={200}
                value={title}
                disabled={busy}
                onChange={(event) => {
                  setTitle(event.target.value);
                  invalidate();
                }}
              />
            </div>
            <div className="field">
              <label htmlFor="source-type">Type</label>
              <select
                id="source-type"
                value={kind}
                disabled={busy}
                onChange={(event) => {
                  setKind(event.target.value as Kind);
                  invalidate();
                }}
              >
                <option value="prompt">Prompt</option>
                <option value="skill">Skill</option>
                <option value="graph">Graph</option>
              </select>
            </div>
            <div className="field">
              <label htmlFor="source-content">Content</label>
              <textarea
                id="source-content"
                required
                spellCheck={false}
                value={content}
                disabled={busy}
                onChange={(event) => {
                  setContent(event.target.value);
                  invalidate();
                }}
              />
            </div>
            <div className="form-actions">
              <Link className="button-link" href="/knowledge">
                Cancel
              </Link>
              <button
                type="submit"
                className="primary"
                disabled={busy || !title.trim() || !content.trim()}
              >
                {generate.isPending
                  ? 'Generating…'
                  : generate.isError
                    ? 'Retry'
                    : preview
                      ? 'Regenerate summary'
                      : 'Generate summary'}
              </button>
            </div>
          </form>
        </Panel>
        <Panel
          title="Summary & tags"
          meta={
            <Pill green={!!preview}>
              {generate.isPending
                ? 'Generating'
                : preview
                  ? 'Ready'
                  : generate.isError
                    ? 'Unavailable'
                    : 'No preview'}
            </Pill>
          }
          className="summary-panel"
        >
          <div className="panel-body">
            {preview ? (
              <>
                <p className="summary-body">{preview.summary}</p>
                <hr className="rule" />
                <Tags tags={preview.tags} />
                <hr className="rule" />
                <Button primary disabled={busy} onClick={() => save.mutate()}>
                  {save.isPending ? 'Saving…' : save.isError ? 'Retry save' : 'Save source'}
                </Button>
              </>
            ) : (
              <p className="muted" role="status">
                {generate.isPending ? 'Generating summary and tags…' : 'No preview available'}
              </p>
            )}
          </div>
        </Panel>
      </div>
    </>
  );
}
