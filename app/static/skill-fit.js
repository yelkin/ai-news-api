import { safeSourceUrl } from './result-data.js';
import { parseTitles } from './job-workflow.js';
import { debugFetch } from './debug-http.js';

export { parseTitles } from './job-workflow.js';

export function validateResumeFile(file) {
  if (!file || !file.name.toLowerCase().endsWith('.txt') || !file.size || file.size > 65536) {
    throw Error('Choose a nonempty UTF-8 .txt resume up to 64 KiB.');
  }
}

/** Search only already-prepared postings; maintenance runs on /jobs/manage. */
export async function runFit(request, api, progress = () => {}) {
  progress('Comparing your qualifications…');
  return api('/jobs/fit', {titles: request.titles, qualification_ids: request.qualification_ids, limit: 10});
}

async function api(path, body) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 600000);
  try {
    // API contracts: /openapi.json and /docs. No resume data is saved in browser storage.
    const response = await debugFetch(path, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body), signal:controller.signal});
    if (!response.ok) {
      const data = await response.json().catch(() => ({}));
      throw Error(typeof data.detail === 'string' ? data.detail : 'Request failed. Check the input and try again.');
    }
    return await response.json();
  } catch (error) {
    if (error.name === 'AbortError') throw Error('This step took too long. Retry to continue completed work.');
    throw error;
  } finally { clearTimeout(timeout); }
}

function node(tag, text, className = '') {
  const el = document.createElement(tag);
  el.textContent = text;
  el.className = className;
  return el;
}

function setup() {
  const $ = id => document.getElementById(id);
  const panel = $('fit-panel'), status = $('fit-status');
  let skills = [], busy = false, generation = 0, titleTimer, titleSequence = 0;
  const announce = text => { status.textContent = text; };
  function reset() { generation++; $('fit-results').replaceChildren(); $('fit-manage-link').hidden = true; }
  function setBusy(value) {
    busy = value;
    panel.setAttribute('aria-busy', String(value));
    for (const el of panel.querySelectorAll('input, button')) el.disabled = value;
  }
  function renderSkills() {
    $('fit-skills').replaceChildren(...skills.map(skill => {
      const chip = node('button', `${skill.canonical_name} ×`, 'skill-chip');
      chip.type = 'button';
      chip.setAttribute('aria-label', `Remove ${skill.canonical_name}`);
      chip.addEventListener('click', () => { skills = skills.filter(s => s.id !== skill.id); reset(); renderSkills(); });
      return chip;
    }));
    $('fit-review').hidden = false;
  }
  $('fit-titles').addEventListener('input', () => {
    reset();
    const seq = ++titleSequence;
    clearTimeout(titleTimer);
    const pieces = $('fit-titles').value.split(';');
    const query = pieces.pop().trim();
    titleTimer = setTimeout(async () => {
      try {
        const response = await debugFetch(`/jobs/titles?q=${encodeURIComponent(query)}&limit=10`);
        if (!response.ok) return;
        const titles = await response.json();
        if (seq !== titleSequence) return;
        $('fit-title-suggestions').replaceChildren(...titles.map(title => {
          const option = document.createElement('option');
          option.value = [...pieces.map(s => s.trim()).filter(Boolean), title].join('; ');
          return option;
        }));
      } catch { /* Free-text titles remain usable without suggestions. */ }
    }, 200);
  });
  $('fit-resume').addEventListener('change', extractResume);
  async function extractResume() {
    if (busy) return;
    reset(); skills = []; $('fit-review').hidden = true;
    const version = generation;
    try {
      const file = $('fit-resume').files[0];
      validateResumeFile(file);
      setBusy(true); announce('Extracting your resume qualifications…');
      const text = new TextDecoder('utf-8', {fatal:true}).decode(await file.arrayBuffer());
      const data = await api('/resume/qualifications', {text});
      if (version !== generation) return;
      skills = data.qualifications;
      renderSkills();
      announce(skills.length ? 'Review your qualifications, then find matching jobs.' : 'No qualifications found. Add a qualification or try a more detailed resume.');
      $('fit-review').focus();
    } catch (error) { announce(error.message); }
    finally { setBusy(false); }
  }
  let skillSequence = 0;
  $('fit-add-skill').addEventListener('input', async () => {
    const seq = ++skillSequence;
    try {
      const response = await debugFetch(`/qualifications?q=${encodeURIComponent($('fit-add-skill').value)}&limit=10`);
      if (!response.ok) return;
      const values = await response.json();
      if (seq !== skillSequence) return;
      $('fit-skill-suggestions').replaceChildren(...values.map(skill => {
        const option = document.createElement('option'); option.value = skill.canonical_name; return option;
      }));
    } catch { /* Resolution also accepts new labels. */ }
  });
  $('fit-add-button').addEventListener('click', async () => {
    if (busy) return;
    const label = $('fit-add-skill').value.trim();
    if (!label || skills.length >= 100) { announce('Enter a qualification; at most 100 may be selected.'); return; }
    setBusy(true);
    try {
      const data = await api('/qualifications/resolve', {labels:[label]});
      skills = [...new Map([...skills, ...data.qualifications].map(q => [q.id, q])).values()];
      reset(); renderSkills(); $('fit-add-skill').value = ''; announce('Qualification added.');
    } catch (error) { announce(error.message); }
    finally { setBusy(false); }
  });
  function renderResults(data) {
    const counts = data.counts;
    const messages = {no_candidates:'No stored jobs match those titles. Update job data or broaden your titles.', preparation_needed:'Matching jobs need preprocessing on the job-data page.', no_overlap:'No evidenced qualification overlap was found. Review your skills or broaden your titles.'};
    announce(`${messages[data.state] || `${data.results.length} matches, ordered by qualification coverage.`} ${counts.prepared} scored, ${counts.pending} pending, ${counts.failed} failed, ${counts.empty} without extracted requirements.${data.semantic_tiebreak_available ? '' : ' Semantic tie-breaking unavailable.'}`);
    $('fit-manage-link').hidden = !(data.state === 'preparation_needed' || counts.pending || counts.failed);
    $('fit-results').replaceChildren(...data.results.map(result => {
      const item = node('li', '', 'result');
      item.append(node('p', result.job.company, 'company-name'), node('h2', result.job.title));
      item.append(node('p', `${result.matched.length} of ${result.matched.length + result.unmatched.length} extracted requirements evidenced`, 'fit-coverage'));
      item.append(node('p', `Matched: ${result.matched.join(', ')}`));
      if (result.unmatched.length) item.append(node('p', `Not found in your resume: ${result.unmatched.join(', ')}`));
      const saved = node('a', 'Stored posting'); saved.href = `/jobs/${result.job.id}`; item.append(saved);
      const url = safeSourceUrl(result.job.source_url);
      if (url) { const link = node('a', 'Original posting'); link.href = url; link.className = 'fit-original'; item.append(link); }
      return item;
    }));
  }
  async function find() {
    if (busy) return;
    const version = generation;
    try {
      const titles = parseTitles($('fit-titles').value);
      if (!skills.length) throw Error('Extract or add at least one qualification first.');
      setBusy(true);
      const data = await runFit({titles, qualification_ids:skills.map(q => q.id)}, api, announce);
      if (version === generation) renderResults(data);
    } catch (error) {
      announce(error.message);
    } finally { setBusy(false); }
  }
  $('fit-find').addEventListener('click', find);
  for (const button of document.querySelectorAll('[data-search-mode]')) button.addEventListener('click', () => {
    if (busy) return;
    const fit = button.dataset.searchMode === 'fit';
    panel.hidden = !fit;
    document.body.classList.toggle('skill-fit-mode', fit);
    $('free-search-panel').hidden = fit;
    $('search-content').hidden = fit;
    for (const tab of document.querySelectorAll('[data-search-mode]')) tab.setAttribute('aria-pressed', String(tab === button));
  });
}
if (typeof document !== 'undefined') setup();
