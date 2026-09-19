export function parseTitles(value) {
  const titles = [...new Set(value.split(';').map(title => title.trim()).filter(Boolean))];
  if (!titles.length || titles.length > 10 || titles.some(title => title.length > 200)) {
    throw Error('Enter 1–10 job titles, each at most 200 characters. Separate titles with semicolons.');
  }
  return titles;
}

/** Refresh once, then preprocess matching jobs in resumable committed batches. */
export async function updateJobs(titles, api, progress = () => {}, stopped = () => false, state = {}) {
  const check = () => {
    if (stopped()) throw Error('Stopped. Choose Resume update to continue.');
  };
  check();
  if (!state.refreshed) {
    progress('Fetching job postings…');
    const summary = await api('/jobs/scrape', {});
    state.refreshed = true;
    state.refreshFailures = summary.failed || 0;
  }
  check();
  while (!state.prepared) {
    progress(`Preparing matching jobs… ${state.processed || 0} processed, ${state.failed || 0} failures.`);
    const batch = await api('/jobs/prepare', {titles, cursor: state.cursor || null});
    state.cursor = batch.next_cursor;
    state.prepared = batch.complete;
    state.processed = (state.processed || 0) + batch.processed;
    state.failed = (state.failed || 0) + batch.failed;
    check();
  }
  return state;
}
