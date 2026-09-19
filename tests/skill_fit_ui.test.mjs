import assert from 'node:assert/strict';
import test from 'node:test';
import { runFit, parseTitles, validateResumeFile } from '../app/static/skill-fit.js';

test('search compares reviewed IDs without refreshing or preprocessing', async () => {
  const calls = [];
  const api = async (path, body) => {
    calls.push([path, body]);
    return {results: [], state: 'no_overlap'};
  };
  await runFit({titles:['SRE'], qualification_ids:[7]}, api);
  assert.deepEqual(calls.map(call => call[0]), ['/jobs/fit']);
  assert.equal(calls[0][1].qualification_ids[0], 7);
});

test('input validation bounds titles and resume upload', () => {
  assert.deepEqual(parseTitles(' SRE ; Platform Engineer; SRE '), ['SRE','Platform Engineer']);
  assert.throws(() => parseTitles(' '));
  assert.throws(() => validateResumeFile({name:'resume.pdf',size:10}));
  assert.throws(() => validateResumeFile({name:'resume.txt',size:65537}));
});
