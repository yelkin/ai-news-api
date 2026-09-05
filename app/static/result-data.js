/** Pure response preparation keeps the API's relevance order intact. */
export function safeSourceUrl(value) {
  if (typeof value !== 'string' || !/^https?:\/\//i.test(value)) return null;
  try {
    const url = new URL(value);
    return ['http:', 'https:'].includes(url.protocol) && !url.username && !url.password ? url.href : null;
  } catch {
    return null;
  }
}

export function normalizeQuery(value) {
  const query = value.trim();
  if (!query) throw new Error('Describe the kind of work you’re looking for.');
  if (query.length > 2000) throw new Error('Keep your search to 2,000 characters or fewer.');
  return query;
}

export function normalizeResponse(data) {
  if (!data || !Array.isArray(data.jobs) || typeof data.answer !== 'string' || !Array.isArray(data.cited_job_ids)) {
    throw new Error('Unexpected search response');
  }
  const jobs = data.jobs.map(job => {
    if (!job || !Number.isSafeInteger(job.id) || job.id < 1) throw new Error('Invalid job response');
    const text = (value, fallback = '') => typeof value === 'string' && value.trim() ? value : fallback;
    const url = safeSourceUrl(job.source_url);
    return {
      id: job.id,
      title: text(job.title, 'Untitled role'),
      company: text(job.company, 'Company not listed'),
      description: text(job.description),
      location: text(job.location),
      remote: job.remote === true,
      url,
      domain: url ? new URL(url).hostname : 'Source link unavailable',
    };
  });
  const byId = new Map(jobs.map(job => [job.id, job]));
  const citations = [...new Set(data.cited_job_ids)].filter(id => byId.has(id)).map(id => byId.get(id));
  return { jobs, answer: data.answer, citations };
}
