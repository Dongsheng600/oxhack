import { suffix, knowledge } from '../fixtures.js';
import { escape, pill, tags, button, heading, url } from './helpers.js';

function sourceLinks(
  {
    theme
  }
) {
  return `<div class="sources"><div class="eyebrow">Referenced knowledge · 2</div>${knowledge.slice(0, 2).map(
  k => `<a class="source-item" href="${url('detail', theme)}"><span class="file-kind">${k.kind.toUpperCase()}</span><span>${k.title}</span><span class="source-arrow" aria-hidden="true">↗</span></a>`
).join('')}</div>`;
}

export function suggestion(context) {
  const {
    state,
    revision,
    selectedOption
  } = context;

  if (state === 'choice' || state === 'diff') return `<section class="suggestion"><div class="suggestion-top"><span class="eyebrow">Clarify</span>${pill('1 question', 'green')}</div><h2>How should the review be delivered?</h2><fieldset class="choice-group"><legend class="sr-only">Review format</legend>${['Prioritized findings', 'Inline comments', 'Implementation plan'].map(
  (x, i) => `<label class="choice ${state === 'diff' && i === selectedOption ? 'selected' : ''}"><input type="radio" name="format" value="${i}" ${state === 'diff' && i === selectedOption ? 'checked' : ''}>${x}</label>`
).join('')}</fieldset>${state === 'diff' ? `<div class="actions">${button('Back', 'choice')}${button('Confirm changes', 'confirm', 'primary')}</div>` : button('Decline all', 'decline', 'decline')}<div class="suggestion-meta"><span>REV ${String(revision).padStart(2, '0')}</span></div></section>${sourceLinks(context)}`;

  if (state === 'error')
    return `<section class="suggestion"><div class="suggestion-top"><span class="eyebrow">Enhancement</span>${pill('Unavailable', 'error')}</div><div class="error-box"><h2>Request timed out</h2><p>Your draft is intact. Retry the request or continue writing.</p></div><div class="actions">${button('Continue writing', 'continue')}${button('Retry', 'retry', 'primary')}</div><div class="suggestion-meta"><span>req_7f10</span><span>HTTP 503</span></div></section>`;

  if (state === 'empty')
    return `<section class="suggestion"><div class="suggestion-top"><span class="eyebrow">Enhancement</span>${pill('Idle')}</div><h2>No draft yet</h2><div class="status-message muted">Enter a prompt to request suggestions.</div><button class="primary" disabled>Enhance</button></section>`;

  if (state === 'none' || state === 'accepted' || state === 'editing')
    return `<section class="suggestion"><div class="suggestion-top"><span class="eyebrow">Enhancement</span>${pill(state === 'editing' ? 'Draft changed' : 'Up to date', 'green')}</div><h2>${state === 'editing' ? 'Ready to check' : 'No suggestion'}</h2>${button('Enhance', 'enhance', 'primary')}<div class="suggestion-meta"><span>REV ${String(revision).padStart(2, '0')}</span><span>${state === 'editing' ? 'Suggestions cleared' : 'Checked just now'}</span></div></section>${state === 'editing' ? '' : sourceLinks(context)}`;

  if (state === 'loading')
    return `<section class="suggestion"><div class="suggestion-top"><span class="eyebrow">Enhancement</span>${pill('Working')}</div><div class="loading-bar"></div><h2>Checking your prompt</h2>${button('Cancel', 'continue')}<div class="suggestion-meta"><span>REV ${String(revision).padStart(2, '0')}</span></div></section>`;

  return `<section class="suggestion"><div class="suggestion-top"><span class="eyebrow">Autocomplete</span>${pill('Suggestion', 'green')}</div><h2>Add evidence to<br class="desktop-only"> each finding.</h2><p class="snippet">${escape(suffix.trim())}</p><div class="actions">${button('Dismiss', 'decline')}${button('Accept <kbd>Tab</kbd>', 'accept', 'primary')}</div><div class="suggestion-meta"><span>REV ${String(revision).padStart(2, '0')}</span><span>Not applied</span></div></section>${sourceLinks(context)}`;
}

export function refine(context) {
  const {
    state,
    draft,
    revision,
    notice,
    undoValue,
    selectedOption,
    optionSuffixes
  } = context;

  const diff = state === 'diff';
  const editable = !['autocomplete', 'diff'].includes(state);
  const editor = diff ? `<div class="diff-content"><div class="diff-block"><div class="diff-label">Original · Revision ${revision}</div>${escape(draft)}</div><div class="diff-block diff-divider"><div class="diff-label">Proposed</div>${escape(draft)}<div class="diff-add"><b>+ Added</b>${escape(optionSuffixes[selectedOption].trim())}</div></div></div>` : `<div class="editor-region">${editable ? `<label class="sr-only" for="draft">Draft prompt</label><textarea id="draft" class="draft-input" placeholder="What would you like Codex to do?" spellcheck="false">${escape(draft)}</textarea>` : `<div class="prompt-display" role="textbox" aria-label="Draft prompt with unaccepted suggestion" tabindex="0">${escape(draft)}<span class="caret"></span><span class="ghost">${escape(suffix)}</span></div>`}</div>`;
  return `${heading('Refine your prompt', pill('Draft', 'green'))}${notice ? `<div class="accepted-banner" role="status">${escape(notice)}${undoValue !== null ? button('Undo', 'undo') : ''}</div>` : ''}<div class="refine-grid"><div><section class="panel draft-card"><div class="panel-head"><span class="eyebrow">${diff ? 'Review changes' : 'Your prompt'}</span><span class="count">${diff ? '+ 1 addition' : `REV ${String(revision).padStart(2, '0')}`}</span></div>${editor}<div class="draft-foot"><span>${diff ? 'Not applied' : `${draft.length} characters`}</span><span>${diff ? '1 option selected' : 'Plain text'}</span></div></section>${diff ? '' : `<div class="prompt-actions"><span>Draft only</span>${button('Copy prompt', 'copy', 'primary')}</div>`}</div><aside>${suggestion(context)}</aside></div><div class="footer-line"><span>${state === 'empty' ? 'No request yet' : `REQUEST ${state === 'error' ? 'req_7f10' : 'req_7f2a'}`}</span><span>Gemini · ${state === 'empty' ? 'Idle' : state === 'error' ? '3,000 ms' : '842 ms'}</span></div>`;
}
