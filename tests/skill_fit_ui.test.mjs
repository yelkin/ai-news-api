import assert from 'node:assert/strict';
import test from 'node:test';
import { runFit, parseTitles, validateResumeFile } from '../app/static/skill-fit.js';

test('skip refresh prepares all batches before matching reviewed IDs', async () => {
  const calls = [];
  const api = async (path, body) => {
    calls.push([path, body]);
    if (path === '/jobs/prepare') return {complete: !!body.cursor, next_cursor: 'next', processed: 1, failed: 0};
    return {results: [], state: 'no_overlap'};
  };
  await runFit({titles:['SRE'], qualification_ids:[7], refresh:false}, api);
  assert.deepEqual(calls.map(c => c[0]), ['/jobs/prepare', '/jobs/prepare', '/jobs/fit']);
  assert.equal(calls[2][1].qualification_ids[0], 7);
});

test('refresh occurs once and resume state avoids repeating it after a failure', async () => {
  const paths = [], state = {};
  let fail = true;
  const api = async path => {
    paths.push(path);
    if (path === '/jobs/prepare' && fail) { fail = false; throw Error('network'); }
    return {complete:true, processed:1, failed:0};
  };
  const request = {titles:['SRE'], qualification_ids:[1], refresh:true};
  await assert.rejects(runFit(request, api, () => {}, () => false, state));
  await runFit(request, api, () => {}, () => false, state);
  assert.equal(paths.filter(p => p === '/jobs/scrape').length, 1);
});

test('stopping between batches prevents fit and preserves cursor', async () => {
  const state = {};
  let stopped = false;
  const api = async () => { stopped = true; return {complete:false, next_cursor:'next', processed:1, failed:0}; };
  await assert.rejects(runFit({titles:['SRE'], qualification_ids:[1]}, api, () => {}, () => stopped, state), /Stopped/);
  assert.equal(state.cursor, 'next');
});

test('input validation bounds titles and resume upload', () => {
  assert.deepEqual(parseTitles(' SRE ; Platform Engineer; SRE '), ['SRE','Platform Engineer']);
  assert.throws(() => parseTitles(' '));
  assert.throws(() => validateResumeFile({name:'resume.pdf',size:10}));
  assert.throws(() => validateResumeFile({name:'resume.txt',size:65537}));
});
