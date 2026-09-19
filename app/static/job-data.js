import { parseTitles, updateJobs } from './job-workflow.js';

async function api(path, body) {
  const response = await fetch(path, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw Error(typeof data.detail === 'string' ? data.detail : 'The update failed. Retry to continue completed work.');
  }
  return response.json();
}

function setup() {
  const $ = id => document.getElementById(id);
  const panel = $('job-data-content');
  let busy = false, stop = false, state = {}, timer, sequence = 0, activeTitles = [];
  const announce = message => { $('update-status').textContent = message; };
  function setBusy(value) {
    busy = value;
    panel.setAttribute('aria-busy', String(value));
    $('update-titles').disabled = value;
    $('update-start').disabled = value;
    $('update-stop').hidden = !value;
    $('update-stop').disabled = !value;
  }
  $('update-titles').addEventListener('input', () => {
    state = {};
    $('update-retry').hidden = true;
    const current = ++sequence;
    clearTimeout(timer);
    const pieces = $('update-titles').value.split(';');
    const query = pieces.pop().trim();
    timer = setTimeout(async () => {
      try {
        const response = await fetch(`/jobs/titles?q=${encodeURIComponent(query)}&limit=10`);
        if (!response.ok) return;
        const titles = await response.json();
        if (current !== sequence) return;
        $('update-title-suggestions').replaceChildren(...titles.map(title => {
          const option = document.createElement('option');
          option.value = [...pieces.map(value => value.trim()).filter(Boolean), title].join('; ');
          return option;
        }));
      } catch { /* Maintainers may still enter a title without suggestions. */ }
    }, 200);
  });
  $('update-stop').addEventListener('click', () => {
    stop = true;
    announce('Stopping after the current batch…');
  });
  async function run(resume = false) {
    if (busy) return;
    try {
      const titles = parseTitles($('update-titles').value);
      if (!resume || titles.join('\n') !== activeTitles.join('\n')) state = {};
      activeTitles = titles;
      stop = false;
      setBusy(true);
      await updateJobs(titles, api, announce, () => stop, state);
      announce(`Update complete. ${state.processed || 0} jobs processed, ${state.failed || 0} preparation failures, ${state.refreshFailures || 0} refresh failures.`);
      $('update-retry').hidden = true;
    } catch (error) {
      announce(error.message);
      $('update-retry').hidden = false;
    } finally { setBusy(false); }
  }
  $('update-start').addEventListener('click', () => run(false));
  $('update-retry').addEventListener('click', () => run(true));
}

if (typeof document !== 'undefined') setup();
