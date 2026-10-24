import { knowledge } from '../fixtures.js';
import { escape, pill, tags, button, heading, url } from './helpers.js';

export function knowledgePage(
  {
    state,
    theme
  }
) {
  const empty = state === 'empty-library';

  return `${heading('Knowledge', button('+ Add source', 'add', 'primary'))}${empty ? `<div class="panel empty-state"><h2>No sources yet</h2>${button('Add source', 'add', 'primary')}</div>` : `<div class="toolbar"><label class="sr-only" for="search">Search knowledge</label><input class="search-field" id="search" type="search" placeholder="Search knowledge"><div class="filter-group"><label class="sr-only" for="kind">Source type</label><select id="kind"><option>All types</option><option>Skill</option><option>Prompt</option><option>Graph</option></select><label class="sr-only" for="tag">Tag</label><select id="tag"><option>All tags</option><option>code-review</option><option>api</option><option>planning</option></select></div></div><section class="panel"><div class="list-head"><span>Source</span><span>Type</span><span>Updated</span><span></span></div><div id="knowledge-list">${knowledgeRows(knowledge, {
  theme
})}</div><div class="list-foot"><span id="source-count">4 sources · 7 tags</span><span>All changes saved</span></div></section>`}<div class="footer-line"><span>TIGER DATA · POSTGRESQL</span><span>${empty ? '0' : '4'} sources indexed</span></div>`;
}

export function knowledgeRows(
  items,
  {
    theme
  }
) {
  return items.length ? items.map(
    k => `<a class="knowledge-row" href="${url('detail', theme)}"><div><span class="knowledge-title">${k.title}</span>${tags(k.tags)}</div><span class="kind">${k.kind}</span><span class="updated">${k.date}</span><span class="arrow" aria-hidden="true">↗</span></a>`
  ).join('') : '<div class="no-results">No matching sources</div>';
}

export function detailPage(
  {
    theme
  }
) {
  const k = knowledge[0];
  return `<a class="breadcrumb-back" href="${url('knowledge', theme)}">← Knowledge</a>${heading(k.title, pill('Indexed', 'green'))}<div class="detail-grid"><section class="panel"><div class="panel-head"><span class="eyebrow">Source</span><span class="count">${k.file}</span></div><pre class="source-content">${escape(k.content)}</pre></section><div class="stack summary-panel"><section class="panel"><div class="panel-head"><span class="eyebrow">Summary</span></div><div class="panel-body"><p class="summary-body">${k.summary}</p><hr class="rule">${tags(k.tags)}</div></section><section class="panel"><div class="panel-body facts"><div class="fact"><span>Type</span><span>Skill</span></div><div class="fact"><span>Updated</span><span>24 Oct 2026</span></div><div class="fact"><span>Version</span><span class="mono">3</span></div><div class="fact"><span>Retrieval</span><span>Enabled</span></div></div></section></div></div>`;
}

export function addPage(
  {
    state,
    theme
  }
) {
  const failed = state === 'import-error';
  return `<a class="breadcrumb-back" href="${url('knowledge', theme)}">← Knowledge</a>${heading('Add knowledge', pill(failed ? 'Import failed' : 'Unsaved', failed ? 'error' : ''))}<div class="form-grid"><section class="panel"><div class="panel-head"><span class="eyebrow">Source details</span><span class="count">${failed ? "01" : "02"} / 02</span></div><form class="panel-body" id="source-form">${failed ? '<div class="import-error" role="alert"><strong>Summary generation failed</strong>Gemini timed out. Source content is preserved. Retry to generate the summary and tags.</div>' : ''}<div class="field"><label for="source-title">Title</label><input id="source-title" value="Review with evidence" required></div><div class="field"><label for="source-type">Type</label><select id="source-type"><option>Prompt</option><option>Skill</option><option>Graph</option></select></div><div class="field"><label for="source-content">Content</label><textarea id="source-content" required spellcheck="false">Review the supplied code.\nFor every finding, include the file location,\nthe observed behavior, and a regression test.\nOrder findings by severity.</textarea></div><div class="form-actions">${button('Cancel', 'knowledge')}<button type="submit" class="primary">${failed ? 'Retry' : 'Regenerate summary'}</button></div></form></section><section class="panel summary-panel"><div class="panel-head"><span class="eyebrow">Summary & tags</span>${pill(failed ? 'Unavailable' : 'Ready')}</div><div class="panel-body">${failed ? '<p class="muted">No preview available</p>' : `<p class="summary-body">Code review guidance that pairs each finding with a file location, observed behavior, and a regression test.</p><hr class="rule">${tags(['code-review', 'testing', 'evidence'])}<hr class="rule"><button class="primary" data-action="save-preview">Save source</button>`}</div></section></div>`;
}
