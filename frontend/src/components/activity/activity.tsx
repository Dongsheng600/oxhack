'use client';
import { useState } from 'react';
import Link from 'next/link';
import { useInfiniteQuery, useQuery } from '@tanstack/react-query';
import { api, errorMessage } from '@/lib/api';
import type { Activity, Page, RequestDetail } from '@/lib/types';
import { Button, ErrorState, Footer, Heading, Loading, Panel, Pill } from '@/components/ui';
import '../knowledge/knowledge.css';
const time = (value: string) => new Date(value).toLocaleTimeString(undefined, { hour12: false });
function CallStatus({ call }: { call: Activity }) {
  return (
    <Pill error={call.status === 'error'} green={call.status !== 'error'}>
      {call.status_code ? `${call.status_code} ` : ''}
      {call.status}
    </Pill>
  );
}
export function ActivityList() {
  const [type, setType] = useState<'api' | 'ai'>('api'),
    [status, setStatus] = useState('all');
  const query = useInfiniteQuery({
    queryKey: ['activity', type, status],
    initialPageParam: '',
    queryFn: ({ pageParam, signal }) =>
      api<Page<Activity>>(
        `/activity/${type}?${new URLSearchParams({ status, limit: '40', ...(pageParam ? { cursor: pageParam } : {}) })}`,
        { signal },
      ),
    getNextPageParam: (last) => last.next_cursor || undefined,
  });
  const items = query.data?.pages.flatMap((page) => page.items) || [];
  return (
    <>
      <Heading action={<Pill>30-day retention</Pill>}>Activity</Heading>
      <div className="toolbar">
        <div
          className="segments"
          role="tablist"
          aria-label="Log type"
          onKeyDown={(event) => {
            if (event.key === 'ArrowLeft' || event.key === 'ArrowRight') {
              event.preventDefault();
              const next = type === 'api' ? 'ai' : 'api';
              setType(next);
              (
                event.currentTarget.querySelector(`[data-type="${next}"]`) as HTMLButtonElement
              )?.focus();
            }
          }}
        >
          {(['api', 'ai'] as const).map((value) => (
            <button
              key={value}
              role="tab"
              data-type={value}
              aria-selected={value === type}
              aria-controls="activity-panel"
              id={`tab-${value}`}
              tabIndex={value === type ? 0 : -1}
              className={value === type ? 'active' : ''}
              onClick={() => setType(value)}
            >
              {value.toUpperCase()} calls
            </button>
          ))}
        </div>
        <div className="filter-group">
          <label className="sr-only" htmlFor="status-filter">
            Status filter
          </label>
          <select
            id="status-filter"
            value={status}
            onChange={(event) => setStatus(event.target.value)}
          >
            <option value="all">All statuses</option>
            <option value="success">Success</option>
            <option value="error">Error</option>
          </select>
        </div>
      </div>
      <div className="activity-meta">
        <span>
          <b>{items.length}</b> calls loaded
        </span>
        <span>
          <b>{items.filter((call) => call.status === 'error').length}</b> errors loaded
        </span>
        <span>Metadata only</span>
        <span>30-day retention</span>
      </div>
      <div role="tabpanel" id="activity-panel" aria-labelledby={`tab-${type}`}>
        <Panel>
          {query.isPending ? (
            <Loading />
          ) : query.isError ? (
            <ErrorState message={errorMessage(query.error)} retry={() => void query.refetch()} />
          ) : (
            <>
              <div className="activity-head">
                <span>Local time</span>
                <span>{type === 'ai' ? 'Operation / model' : 'Endpoint / request'}</span>
                <span>Status</span>
                <span>Latency</span>
                <span>{type === 'ai' ? 'Tokens' : 'Request'}</span>
              </div>
              {items.length ? (
                items.map((call) => (
                  <Link
                    href={`/activity/${encodeURIComponent(call.request_id)}`}
                    className="activity-row"
                    key={call.id}
                  >
                    <span className="time mono">{time(call.timestamp)}</span>
                    <div className="activity-operation">
                      {call.operation}
                      <small>{type === 'ai' ? call.model || 'Unavailable' : call.request_id}</small>
                    </div>
                    <span className="status">
                      <CallStatus call={call} />
                    </span>
                    <span className="latency mono">{call.latency_ms.toLocaleString()} ms</span>
                    <span className="tokens mono">
                      {type === 'ai'
                        ? `${call.input_tokens ?? '—'} / ${call.output_tokens ?? '—'}`
                        : call.request_id.slice(-8)}
                    </span>
                  </Link>
                ))
              ) : (
                <div className="no-results">No matching calls</div>
              )}
              <div className="list-foot">
                <span>Metadata only</span>
                <span>{items.length} events loaded</span>
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
            </>
          )}
        </Panel>
      </div>
      <Footer left={type === 'ai' ? 'MODEL CALLS' : 'HTTP REQUESTS'} right="Payload logging off" />
    </>
  );
}
export function ActivityDetail({ id }: { id: string }) {
  const query = useQuery({
    queryKey: ['request', id],
    queryFn: ({ signal }) =>
      api<RequestDetail>(`/activity/requests/${encodeURIComponent(id)}`, { signal }),
  });
  const data = query.data,
    first = data?.api_calls[0];
  return (
    <>
      <Link className="breadcrumb-back" href="/activity">
        ← Activity
      </Link>
      <Heading action={first && <CallStatus call={first} />}>Request detail</Heading>
      {query.isPending ? (
        <Loading />
      ) : query.isError ? (
        <ErrorState message={errorMessage(query.error)} retry={() => void query.refetch()} />
      ) : (
        data && (
          <>
            <div className="detail-grid">
              <div className="stack">
                <Panel
                  title={first?.operation || 'Request'}
                  meta={<span className="count break-all">{data.request_id}</span>}
                >
                  <dl className="event-details">
                    {[
                      ['Request ID', data.request_id],
                      [
                        'Timestamp',
                        first ? new Date(first.timestamp).toLocaleString() : 'Unavailable',
                      ],
                      ['Latency', first ? `${first.latency_ms} ms` : 'Unavailable'],
                      ['Expires', new Date(data.expires_at).toLocaleString()],
                      ['API calls', data.api_calls.length],
                      ['AI calls', data.ai_calls.length],
                      ['Payload logging', 'Disabled'],
                    ].map(([label, value]) => (
                      <div className="item" key={label}>
                        <dt>{label}</dt>
                        <dd>{value}</dd>
                      </div>
                    ))}
                  </dl>
                </Panel>
                {data.api_calls.length > 0 && (
                  <Panel title="API calls">
                    <div className="panel-body">
                      {data.api_calls.map((call) => (
                        <div className="timeline-row" key={call.id}>
                          <span className="dot" />
                          <div>
                            {call.operation}
                            <small>
                              {call.status}
                              {call.error_code ? ` · ${call.error_code}` : ''}
                            </small>
                          </div>
                          <span className="mono">{call.latency_ms} ms</span>
                        </div>
                      ))}
                    </div>
                  </Panel>
                )}
              </div>
              <div className="stack">
                <Panel
                  title="AI calls"
                  meta={<span className="count">{data.ai_calls.length} spans</span>}
                >
                  <div className="panel-body">
                    {data.ai_calls.length ? (
                      data.ai_calls.map((call) => (
                        <div className="timeline-row" key={call.id}>
                          <span className="dot" />
                          <div>
                            {call.operation}
                            <small>{call.model || 'Model unavailable'}</small>
                            <small>
                              {call.status} · {call.input_tokens ?? '—'} /{' '}
                              {call.output_tokens ?? '—'} tokens
                              {call.error_code ? ` · ${call.error_code}` : ''}
                            </small>
                          </div>
                          <span className="mono">{call.latency_ms} ms</span>
                        </div>
                      ))
                    ) : (
                      <p className="muted">No AI calls</p>
                    )}
                  </div>
                </Panel>
                {data.sources.length > 0 && (
                  <Panel title="Referenced knowledge">
                    <div className="panel-body">
                      {data.sources.map((source) => (
                        <Link
                          className="source-item"
                          href={`/knowledge/${encodeURIComponent(source.id)}`}
                          key={source.id}
                        >
                          <span>{source.title}</span>
                          <span className="mono">v{source.version}</span>
                        </Link>
                      ))}
                    </div>
                  </Panel>
                )}
              </div>
            </div>
            <Footer left="Metadata only" right="30-day retention" />
          </>
        )
      )}
    </>
  );
}
