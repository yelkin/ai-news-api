import assert from 'node:assert/strict';
import test from 'node:test';

import { safeSourceUrl, normalizeResponse, normalizeQuery } from "../app/static/result-data.js";

test('only absolute HTTP(S) original posting links are clickable', () => {
  assert.equal(safeSourceUrl('https://jobs.example/a?q=1'), 'https://jobs.example/a?q=1');
  for (const url of ['javascript:alert(1)', 'data:text/html,test', '/jobs/1', '//example.com', 'https://', '', null]) {
    assert.equal(safeSourceUrl(url), null);
  }
});

test('search validation matches the API and trims the submitted query', () => {
  assert.equal(normalizeQuery('  Python roles  '), 'Python roles');
  assert.throws(() => normalizeQuery('   '));
  assert.throws(() => normalizeQuery('x'.repeat(2001)));
});

test('view data preserves relevance order and associates only returned citations', () => {
  const result = normalizeResponse({
    answer: '<b>Use these jobs</b>', cited_job_ids: [8, 100, 8],
    jobs: [
      { id: 8, title: 'Closest', company: 'Example', source_url: 'https://example.com/job', description: '<b>Python</b>' },
      { id: 2, title: 'Next', source_url: 'javascript:alert(1)', description: 'Go' },
    ],
  });
  assert.deepEqual(result.jobs.map(job => job.id), [8, 2]);
  assert.equal(result.answer, '<b>Use these jobs</b>');
  assert.equal(result.jobs[1].url, null);
  assert.deepEqual(result.citations.map(job => job.id), [8]);
  assert.equal(result.jobs[0].description, '<b>Python</b>');
});

test('empty results are valid but malformed responses are errors', () => {
  assert.deepEqual(normalizeResponse({jobs: [], answer: 'None', cited_job_ids: []}).jobs, []);
  for (const data of [null, {}, {jobs: 'wrong', answer: 'a'}, {jobs: [null], answer: 'a', cited_job_ids: []}]) {
    assert.throws(() => normalizeResponse(data));
  }
});
