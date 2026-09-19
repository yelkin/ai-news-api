import assert from 'node:assert/strict';
import test from 'node:test';

import { clearDebugEntries, debugEntries, debugFetch } from '../app/static/debug-http.js';

test('captures complete successful HTTP exchanges in order', async () => {
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async request => new Response(
    JSON.stringify({echo: await request.text()}),
    {status: 201, statusText: 'Created', headers: {'Content-Type': 'application/json'}},
  );
  clearDebugEntries();
  try {
    const response = await debugFetch('https://example.test/jobs/search', {
      method: 'POST',
      headers: {'Content-Type': 'application/json', 'X-Debug': 'yes'},
      body: '{"query":"SRE"}',
    });
    assert.equal(response.status, 201);
    assert.equal(debugEntries().length, 1);
    const entry = debugEntries()[0];
    assert.equal(entry.request.method, 'POST');
    assert.equal(entry.request.url, 'https://example.test/jobs/search');
    assert.match(entry.request.headers, /content-type: application\/json/);
    assert.equal(entry.request.body, '{"query":"SRE"}');
    assert.equal(entry.response.status, 201);
    assert.match(entry.response.headers, /content-type: application\/json/);
    assert.equal(entry.response.body, '{"echo":"{\\"query\\":\\"SRE\\"}"}');
  } finally {
    globalThis.fetch = originalFetch;
    clearDebugEntries();
  }
});

test('retains the raw request and network error for failed calls', async () => {
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async () => { throw new TypeError('connection lost'); };
  clearDebugEntries();
  try {
    await assert.rejects(debugFetch('https://example.test/jobs/titles?q=SRE'), /connection lost/);
    const entry = debugEntries()[0];
    assert.equal(entry.request.method, 'GET');
    assert.equal(entry.response, null);
    assert.equal(entry.error, 'TypeError: connection lost');
  } finally {
    globalThis.fetch = originalFetch;
    clearDebugEntries();
  }
});
