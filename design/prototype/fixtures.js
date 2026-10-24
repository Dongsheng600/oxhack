// Design fixtures only. These are not persisted knowledge or live service results.
export const prompt = 'Review the authentication flow in this pull request. Focus on session expiry and redirect handling.';
export const suffix = ' Include file references and a regression test for each finding.';
export const choiceSuffix = '\nReturn findings ordered by severity, with file references and suggested regression tests.';
export const knowledge = [
  { title: 'Security review', file: 'security-review.md', kind: 'Skill', tags: ['code-review', 'security'], date: '24 Oct', summary: 'Reviews session lifetime, redirect validation, and authentication boundaries. Requires evidence for each finding and a focused regression test.', content: '# Security review\n\n## Review scope\nInspect session expiry, token refresh,\nand redirect destinations.\n\n## Evidence\nFor each finding, include:\n- The file and affected behavior\n- An observable failure scenario\n- A focused regression test\n\n## Constraints\nDo not infer vulnerabilities without\nevidence in the provided code.' },
  { title: 'Review with evidence', file: 'review-with-evidence.md', kind: 'Prompt', tags: ['code-review', 'testing'], date: '23 Oct' },
  { title: 'API design checklist', file: 'api-design.md', kind: 'Skill', tags: ['api', 'python'], date: '22 Oct' },
  { title: 'Clarify a task', file: 'clarify-task.json', kind: 'Graph', tags: ['planning', 'constraints'], date: '21 Oct' }
];
export const calls = [
  { time: '14:32:08', api: 'POST /v1/enhance', operation: 'Generate suggestion', model: 'Gemini · generation', id: 'req_7f2a', status: '200 OK', latency: '842 ms', tokens: '1,284' },
  { time: '14:32:07', api: 'POST /v1/enhance', operation: 'Review relevance', model: 'Gemini · relevance', id: 'req_7f29', status: '200 OK', latency: '164 ms', tokens: '420' },
  { time: '14:32:06', api: 'POST /v1/enhance', operation: 'Extract tags', model: 'Gemini · tagging', id: 'req_7f28', status: '200 OK', latency: '118 ms', tokens: '226' },
  { time: '14:30:42', api: 'POST /v1/enhance', operation: 'Generate suggestion', model: 'Gemini · generation', id: 'req_7f10', status: '503 Error', latency: '3,000 ms', tokens: '—' },
  { time: '14:28:16', api: 'POST /v1/knowledge', operation: 'Summarize knowledge', model: 'Gemini · ingestion', id: 'req_7ef3', status: '201 OK', latency: '612 ms', tokens: '908' }
];
export const screens = [
  ['01','autocomplete','Refine · Autocomplete'], ['02','choice','Refine · Multiple choice'],
  ['03','diff','Refine · Confirm diff'], ['04','none','Refine · No suggestion'],
  ['05','error','Refine · Service error'], ['06','knowledge','Knowledge · Library'],
  ['07','detail','Knowledge · Source'], ['08','add','Knowledge · Add source'],
  ['09','api','Activity · API calls'], ['10','ai','Activity · AI calls'],
  ['11','event','Activity · Request detail'], ['12','settings','Settings'],
  ['13','empty','Refine · Empty draft'], ['14','empty-library','Knowledge · Empty library'],
  ['15','import-error','Knowledge · Ingestion error']
];
