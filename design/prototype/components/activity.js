import { calls } from '../fixtures.js';
import { escape, pill, tags, button, heading, url } from './helpers.js';

export function activityPage(
  {
    state,
    theme
  }
) {
  const ai = state === 'ai';

  return `${heading('Activity', pill('Last 24 hours'))}<div class="toolbar"><div class="segments" role="tablist" aria-label="Log type"><button role="tab" aria-selected="${!ai}" class="${ai ? '' : 'active'}" data-action="api">API calls</button><button role="tab" aria-selected="${ai}" class="${ai ? 'active' : ''}" data-action="ai">AI calls</button></div><div class="filter-group"><label class="sr-only" for="status-filter">Status filter</label><select id="status-filter"><option>All statuses</option><option>Success</option><option>Error</option></select></div></div><div class="activity-meta"><span><b>5</b> calls</span><span><b>1</b> error</span><span>Metadata only</span><span>30-day retention</span></div><section class="panel"><div class="activity-head"><span>Time · BST</span><span>${ai ? 'Operation / model' : 'Endpoint / request'}</span><span>Status</span><span>Latency</span><span>${ai ? 'Tokens' : 'Request'}</span></div><div id="activity-list">${activityRows(calls, ai, {
  theme
})}</div><div class="list-foot"><span>24 OCT 2026</span><span>5 events</span></div></section><div class="footer-line"><span>${ai ? 'MODEL CALLS' : 'HTTP REQUESTS'}</span><span>Payload logging off</span></div>`;
}

export function activityRows(
  items,
  ai,
  {
    theme
  }
) {
  return items.map(
    c => `<a class="activity-row" href="${url('event', theme)}"><span class="time mono">${c.time}</span><div class="activity-operation">${ai ? c.operation : c.api}<small>${ai ? c.model : c.id}</small></div><span class="status">${pill(c.status, c.status.includes('Error') ? 'error' : 'green')}</span><span class="latency mono">${c.latency}</span><span class="tokens mono">${ai ? c.tokens : c.id.slice(4)}</span></a>`
  ).join('') || '<div class="no-results">No matching events</div>';
}

export function eventPage(
  {
    theme
  }
) {
  return `<a class="breadcrumb-back" href="${url('api', theme)}">← Activity</a>${heading('Request detail', pill('200 OK', 'green'))}<div class="detail-grid"><section class="panel"><div class="panel-head"><span class="eyebrow">POST /v1/enhance</span><span class="count">req_7f2a</span></div><dl class="event-details">${[
  ['Timestamp', '24 Oct 2026 · 14:32:08 BST'],
  ['Latency', '842 ms'],
  ['Request ID', 'req_7f2a'],
  ['Prompt revision', '7'],
  ['Response type', 'multiple_choice'],
  ['Retrieved / retained', '4 / 2 sources'],
  ['Input / output tokens', '1,106 / 178'],
  ['Expires', '23 Nov 2026 · 13:32:08 GMT']
].map(([k, v]) => `<div class="item"><dt>${k}</dt><dd>${v}</dd></div>`).join('')}<div class="item wide"><dt>Payload logging</dt><dd>Disabled</dd></div></dl></section><section class="panel"><div class="panel-head"><span class="eyebrow">AI calls</span><span class="count">4 spans</span></div><div class="panel-body">${[
  ['Extract tags', 'Gemini · tagging', '118 ms'],
  ['Review source 1', 'Gemini · relevance', '82 ms'],
  ['Review source 2', 'Gemini · relevance', '82 ms'],
  ['Generate suggestion', 'Gemini · generation', '560 ms']
].map(
  ([a, b, c]) => `<div class="timeline-row"><span class="dot"></span><div>${a}<small>${b}</small></div><span class="mono">${c}</span></div>`
).join('')}</div></section></div>`;
}
