import { debugEntries, subscribeToDebugEntries } from './debug-http.js';

function exchangeText(entry, index) {
  const requestHeaders = entry.request.headers ? `${entry.request.headers}\n` : '';
  const requestBody = entry.request.body ? `\n${entry.request.body}` : '';
  let outcome = 'Pending response…';
  if (entry.response) {
    const responseHeaders = entry.response.headers ? `${entry.response.headers}\n` : '';
    const responseBody = entry.response.body ? `\n${entry.response.body}` : '';
    outcome = `HTTP ${entry.response.status} ${entry.response.statusText}\n${responseHeaders}${responseBody}`;
  } else if (entry.error) {
    outcome = `NETWORK ERROR\n${entry.error}`;
  }
  return `#${index + 1} · ${entry.startedAt} · ${entry.durationMs ?? 'pending'} ms\n${entry.request.method} ${entry.request.url}\n${requestHeaders}${requestBody}\n\n${outcome}`;
}

function setup() {
  const dialog = document.getElementById('debug-dialog');
  const output = document.getElementById('debug-entries');
  const count = document.getElementById('debug-count');
  const render = () => {
    const entries = debugEntries();
    count.textContent = `${entries.length} HTTP ${entries.length === 1 ? 'exchange' : 'exchanges'}`;
    output.replaceChildren(...entries.map((entry, index) => {
      const item = document.createElement('li');
      const raw = document.createElement('pre');
      raw.textContent = exchangeText(entry, index);
      item.append(raw);
      return item;
    }));
    document.getElementById('debug-empty').hidden = entries.length !== 0;
  };
  subscribeToDebugEntries(render);
  document.getElementById('debug-open').addEventListener('click', () => {
    render();
    dialog.showModal();
  });
  document.getElementById('debug-close').addEventListener('click', () => dialog.close());
  dialog.addEventListener('click', event => {
    if (event.target === dialog) dialog.close();
  });
  render();
}

if (typeof document !== 'undefined') setup();
