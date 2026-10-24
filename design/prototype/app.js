import { prompt, suffix, choiceSuffix, knowledge, calls } from './fixtures.js';
import { refine, suggestion } from './components/refine.js';
import { knowledgePage, knowledgeRows, detailPage, addPage } from './components/knowledge.js';
import { activityPage, activityRows, eventPage } from './components/activity.js';
import { settingsPage } from './components/settings.js';
const params = new URLSearchParams(location.search);
let state = params.get('screen') || 'autocomplete';
let theme = params.get('theme') || 'light';
let draft = state === 'empty' ? '' : prompt;
let revision = state === 'empty' ? 0 : 7;
let undoValue = null;
let notice = '';
let selectedOption = 0;

const optionSuffixes = [
  choiceSuffix,
  '\nReturn inline comments anchored to the affected lines, each with supporting evidence.',
  '\nReturn an implementation plan with ordered changes and a regression test for each change.'
];

const url = screen => `app.html?screen=${screen}&theme=${theme}`;

const tabs = [
  ['Refine', 'autocomplete'],
  ['Knowledge', 'knowledge'],
  ['Activity', 'api'],
  ['Settings', 'settings']
];

const pageOf = () => ['knowledge', 'detail', 'add', 'empty-library', 'import-error'].includes(state) ? 'Knowledge' : ['api', 'ai', 'event'].includes(state) ? 'Activity' : state === 'settings' ? 'Settings' : 'Refine';

function viewContext() {
  return {
    state,
    theme,
    draft,
    revision,
    notice,
    undoValue,
    selectedOption,
    optionSuffixes
  };
}

function render() {
  document.documentElement.dataset.theme = theme;
  const current = pageOf();

  document.querySelector('#navigation').innerHTML = tabs.map(
    ([name, screen], i) => `<a class="nav-item ${current === name ? 'active' : ''}" href="${url(screen)}" ${current === name ? 'aria-current="page"' : ''}><span class="num">0${i + 1}</span>${name}</a>`
  ).join('');

  document.querySelector('#breadcrumb').textContent = current;
  document.querySelector('#content').innerHTML = current === 'Refine' ? refine(viewContext()) : state === 'detail' ? detailPage(viewContext()) : ['add', 'import-error'].includes(state) ? addPage(viewContext()) : current === 'Knowledge' ? knowledgePage(viewContext()) : state === 'event' ? eventPage(viewContext()) : current === 'Activity' ? activityPage(viewContext()) : settingsPage(viewContext());
  attach();
}

function go(next) {
  state = next;
  notice = '';
  render();
}

function mutate(value) {
  undoValue = draft;
  draft = value;
  revision++;
  state = 'accepted';
  notice = 'Changes applied to your draft';
  render();
}

function attach() {
  document.querySelectorAll('[data-action]').forEach(el => el.addEventListener('click', async event => {
    event.preventDefault();
    const action = el.dataset.action;

    if (action === 'accept')
      return mutate(draft + suffix);

    if (action === 'confirm')
      return mutate(draft + optionSuffixes[selectedOption]);

    if (action === 'undo') {
      const previous = undoValue;
      undoValue = null;
      draft = previous;
      revision++;
      state = 'none';
      notice = 'Changes undone';
      return render();
    }

    if (action === 'decline') {
      state = 'none';
      notice = 'Suggestion dismissed. Draft unchanged.';
      return render();
    }

    if (action === 'save-preview') {
      el.textContent = 'Design preview only';
      el.disabled = true;
      return;
    }

    if (action === 'copy') {
      try {
        await navigator.clipboard.writeText(draft);
        el.textContent = 'Copied';
      } catch {
        el.textContent = 'Select and copy draft';
      }

      return;
    }

    if (action === 'continue')
      return go('editing');

    if (action === 'retry' || action === 'enhance')
      return go('loading');

    go(action);
  }));

  document.querySelectorAll('input[name=format]').forEach(el => el.addEventListener('change', () => {
    selectedOption = Number(el.value);
    go('diff');
  }));

  const input = document.querySelector('#draft');

  if (input) input.addEventListener('input', () => {
    draft = input.value;
    revision++;
    document.querySelector('.draft-foot span').textContent = `${draft.length} characters`;
    document.querySelector('.panel-head .count').textContent = `REV ${String(revision).padStart(2, '0')}`;

    if (state !== 'editing') {
      state = 'editing';
      document.querySelector('.refine-grid>aside').innerHTML = suggestion(viewContext());
      attachSuggestion();
    }
  });

  const display = document.querySelector('.prompt-display');

  if (display) {
    display.addEventListener('keydown', event => {
      if (event.key === 'Tab') {
        event.preventDefault();
        mutate(draft + suffix);
      } else if (event.key === 'Escape') {
        go('none');
      } else if (event.key.startsWith('Arrow') || event.key.length === 1) {
        go('editing');
        document.querySelector('#draft').focus();
      }
    });

    display.addEventListener('click', () => {
      go('editing');
      document.querySelector('#draft').focus();
    });
  }

  const search = document.querySelector('#search');

  if (search) {
    const filter = () => {
      const type = document.querySelector('#kind').value;
      const tag = document.querySelector('#tag').value;

      const items = knowledge.filter(
        k => (k.title + ' ' + k.tags.join(' ')).toLowerCase().includes(search.value.toLowerCase()) && (type === 'All types' || k.kind === type) && (tag === 'All tags' || k.tags.includes(tag))
      );

      document.querySelector('#knowledge-list').innerHTML = knowledgeRows(items, viewContext());
      document.querySelector('#source-count').textContent = `${items.length} sources`;
    };

    search.addEventListener('input', filter);
    document.querySelector('#kind').addEventListener('change', filter);
    document.querySelector('#tag').addEventListener('change', filter);
  }

  document.querySelector('#status-filter')?.addEventListener('change', event => {
    document.querySelector('#activity-list').innerHTML = activityRows(calls.filter(
      c => event.target.value === 'All statuses' || (c.status.includes('Error') ? event.target.value === 'Error' : event.target.value === 'Success')
    ), state === 'ai', viewContext());
  });

  document.querySelector('#theme')?.addEventListener('change', event => {
    theme = event.target.value === 'system' ? (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light') : event.target.value;
    render();
  });

  document.querySelector('#source-form')?.addEventListener('submit', event => {
    event.preventDefault();
    if (state === 'import-error') return go('add');
    const submit = event.target.querySelector('[type=submit]');
    submit.textContent = 'Preview generated';
    const save = document.querySelector('[data-action=save-preview]');
    save.disabled = false;

    save.onclick = () => {
      save.textContent = 'Design preview only';
      save.disabled = true;
    };
  });
}

function attachSuggestion() {
  document.querySelector('.refine-grid>aside [data-action=enhance]')?.addEventListener('click', () => go('loading'));
}

render();
