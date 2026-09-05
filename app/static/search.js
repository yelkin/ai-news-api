import { normalizeQuery, normalizeResponse } from './result-data.js';

/** As a job seeker, I can describe my next job and follow relevant posting links. */
const form = document.querySelector('#search-form');
const input = document.querySelector('#query');
const submit = document.querySelector('#search-button');
const status = document.querySelector('#status');
const results = document.querySelector('#results');
const summary = document.querySelector('#summary-panel');
const resultsPanel = document.querySelector('#results-panel');
const emptyPanel = document.querySelector('#empty-panel');
const errorPanel = document.querySelector('#error-panel');
let pending = false;

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function descriptionText(html) {
  // A template is inert: never attach supplied HTML or its nodes to the page.
  const template = document.createElement('template');
  template.innerHTML = html;
  template.content.querySelectorAll('script, style, template, noscript').forEach(node => node.remove());
  template.content.querySelectorAll('br, p, div, li, h1, h2, h3, section').forEach(node => node.append(' '));
  const text = (template.content.textContent || '').replace(/\s+/g, ' ').trim();
  return text.length > 320 ? `${text.slice(0, 317).trimEnd()}…` : text;
}

function renderJob(job) {
  const item = element('li', 'result');
  item.id = `job-${job.id}`;
  const source = element('div', 'result-source');
  const badge = element('span', 'company-icon', [...job.company][0].toUpperCase());
  badge.setAttribute('aria-hidden', 'true');
  const sourceText = element('div');
  sourceText.append(element('p', 'company-name', job.company), element('p', 'source-domain', job.domain));
  source.append(badge, sourceText);
  const title = element('h2');
  if (job.url) {
    const link = element('a', '', job.title);
    link.href = job.url;
    title.append(link);
  } else {
    title.textContent = job.title;
  }
  const metadata = [job.location, job.remote ? 'Remote' : ''].filter(Boolean).join(' · ');
  item.append(source, title);
  if (metadata) item.append(element('p', 'result-meta', metadata));
  const description = descriptionText(job.description);
  if (description) item.append(element('p', 'result-description', description));
  return item;
}

function clearResults() {
  for (const panel of [summary, resultsPanel, emptyPanel, errorPanel]) panel.hidden = true;
  results.replaceChildren();
  document.querySelector('#summary-text').textContent = '';
  document.querySelector('#citations').replaceChildren();
}

function showResults(data) {
  status.textContent = `${data.jobs.length} ${data.jobs.length === 1 ? 'result' : 'results'} shown · Ordered by relevance`;
  if (!data.jobs.length) {
    emptyPanel.hidden = false;
    return;
  }
  const summaryText = document.querySelector('#summary-text');
  summaryText.textContent = data.answer;
  summary.hidden = !data.answer.trim();
  const citations = document.querySelector('#citations');
  for (const job of data.citations) {
    const link = element('a', '', job.title);
    link.href = `#job-${job.id}`;
    citations.append(link);
  }
  results.replaceChildren(...data.jobs.map(renderJob));
  resultsPanel.hidden = false;
}

input.addEventListener('input', () => input.setCustomValidity(''));
for (const example of document.querySelectorAll('[data-example]')) {
  example.addEventListener('click', () => {
    if (pending) return;
    input.value = example.dataset.example;
    input.setCustomValidity('');
    input.focus();
  });
}

document.querySelector('#retry-button').addEventListener('click', () => form.requestSubmit());
form.addEventListener('submit', async event => {
  event.preventDefault();
  if (pending) return;
  let query;
  try {
    query = normalizeQuery(input.value);
  } catch (error) {
    input.setCustomValidity(error.message);
    input.reportValidity();
    return;
  }
  input.value = query;
  pending = true;
  submit.disabled = true;
  input.readOnly = true;
  submit.textContent = 'Searching…';
  resultsPanel.setAttribute('aria-busy', 'true');
  document.body.classList.add('has-searched');
  clearResults();
  status.textContent = 'Looking for your next opportunity…';
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 240000);
  try {
    // API contract: /openapi.json, POST /jobs/search (also documented at /docs).
    const response = await fetch('/jobs/search', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query, limit: 10 }),
      signal: controller.signal,
    });
    if (!response.ok) throw new Error('Search request failed');
    showResults(normalizeResponse(await response.json()));
  } catch (error) {
    status.textContent = 'Search unsuccessful. Your query is ready to retry.';
    document.querySelector('#error-message').textContent = error.name === 'AbortError'
      ? 'This search is taking longer than expected. Please try again.'
      : 'We couldn’t complete your search. Check your connection and try again in a moment.';
    errorPanel.hidden = false;
  } finally {
    clearTimeout(timeout);
    pending = false;
    submit.disabled = false;
    submit.textContent = 'Search →';
    input.readOnly = false;
    resultsPanel.setAttribute('aria-busy', 'false');
  }
});
