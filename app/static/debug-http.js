const entries = [];
const listeners = new Set();

function headers(headersValue) {
  return [...headersValue.entries()].map(([name, value]) => `${name}: ${value}`).join('\n');
}

function notify() {
  for (const listener of listeners) listener(entries);
}

/** Fetch while retaining the complete application HTTP exchange for this page load. */
export async function debugFetch(input, init) {
  const request = new Request(input, init);
  const startedAt = new Date().toISOString();
  const started = performance.now();
  const entry = {
    startedAt,
    durationMs: null,
    request: {
      method: request.method,
      url: request.url,
      headers: headers(request.headers),
      body: await request.clone().text(),
    },
    response: null,
    error: null,
  };
  entries.push(entry);
  notify();
  try {
    const response = await fetch(request);
    entry.durationMs = Math.round(performance.now() - started);
    entry.response = {
      status: response.status,
      statusText: response.statusText,
      headers: headers(response.headers),
      body: await response.clone().text(),
    };
    notify();
    return response;
  } catch (error) {
    entry.durationMs = Math.round(performance.now() - started);
    entry.error = error instanceof Error ? `${error.name}: ${error.message}` : String(error);
    notify();
    throw error;
  }
}

export function debugEntries() {
  return entries;
}

export function subscribeToDebugEntries(listener) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function clearDebugEntries() {
  entries.length = 0;
  notify();
}
