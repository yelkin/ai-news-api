import assert from 'node:assert/strict';
import test from 'node:test';

import { parseTitles, updateJobs } from '../app/static/job-workflow.js';

test('job update refreshes once and prepares every batch', async () => {
  const calls = [];
  const api = async (path, body) => {
    calls.push([path, body]);
    if (path === '/jobs/scrape') return {failed: 1};
    return body.cursor
      ? {complete:true, next_cursor:null, processed:2, failed:0}
      : {complete:false, next_cursor:'next', processed:5, failed:1};
  };
  const state = await updateJobs(['SRE'], api);
  assert.deepEqual(calls.map(call => call[0]), ['/jobs/scrape', '/jobs/prepare', '/jobs/prepare']);
  assert.equal(state.processed, 7);
  assert.equal(state.failed, 1);
  assert.equal(state.refreshFailures, 1);
});

test('stopped update resumes without repeating refresh or completed batches', async () => {
  const calls = [], state = {};
  let stopped = false;
  const api = async path => {
    calls.push(path);
    if (path === '/jobs/prepare') {
      stopped = true;
      return {complete:false, next_cursor:'next', processed:5, failed:0};
    }
    return {failed:0};
  };
  await assert.rejects(updateJobs(['SRE'], api, () => {}, () => stopped, state), /Stopped/);
  stopped = false;
  const resumeApi = async (path, body) => {
    calls.push(path);
    assert.equal(body.cursor, 'next');
    return {complete:true, next_cursor:null, processed:1, failed:0};
  };
  await updateJobs(['SRE'], resumeApi, () => {}, () => false, state);
  assert.deepEqual(calls, ['/jobs/scrape', '/jobs/prepare', '/jobs/prepare']);
  assert.equal(state.processed, 6);
});

test('title parsing is shared and bounded', () => {
  assert.deepEqual(parseTitles(' SRE ; Platform Engineer; SRE '), ['SRE', 'Platform Engineer']);
  assert.throws(() => parseTitles(' '));
  assert.throws(() => parseTitles('x'.repeat(201)));
});
