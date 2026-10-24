export const escape = value => String(value).replace(/[&<>"']/g, char => (({
  '&': '&amp;',
  '<': '&lt;',
  '>': '&gt;',
  '"': '&quot;',
  '\'': '&#39;'
})[char]));

export const pill = (label, type = '') => `<span class="pill ${type}">${type === 'green' ? '<span class="dot"></span>' : ''}${escape(label)}</span>`;
export const tags = values => `<div class="tag-list">${values.map(tag => `<span class="tag">${escape(tag)}</span>`).join('')}</div>`;
export const button = (label, action, style = '') => `<button class="${style}" data-action="${action}">${label}</button>`;
export const url = (screen, theme) => `app.html?screen=${screen}&theme=${theme}`;

export function heading(title, extra = '') {
  return `<div class="page-heading"><h1>${title}</h1>${extra}</div>`;
}
