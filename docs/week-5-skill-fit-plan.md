# Week 5 skill-fit implementation plan

Status: implemented after Plannotator feedback. Automated validation passed: 47 Python tests, 8 JavaScript tests, Ruff formatting and Python error checks. Visual browser verification remains pending because no browser is connected. Based on `design/55-week-5-skill-fit.md` and the existing application.

## Outcome and acceptance scenario

On the main page, select one or more job titles using suggestions from stored postings, upload a plain-text resume, review its extracted qualifications, optionally refresh the board, and see jobs ranked by qualification fit.

Acceptance example: a resume with Python, Linux, and Kubernetes ranks an SRE job requiring those three skills above an SRE job requiring Java and AWS. A Python marketing job is excluded by the title filter. Skipping refresh makes no scrape request.

## Proposed scope and decisions

- Reuse FastAPI, SQLModel, Alembic, PostgreSQL/pgvector, and the static frontend. Preserve current API contracts and offer existing free-text search as an alternate page mode.
- First pre-filter jobs in SQL by the requested job titles. Only those candidates enter preparation and qualification ranking; unrelated titles cannot enter through semantic similarity. Rank the filtered candidates primarily by deterministic qualification coverage: matched distinct job requirements divided by all distinct extracted job requirements. Use existing document embedding similarity only to break ties, then internal job ID. Similarity is not a skill percentage or hiring probability.
- Normalize qualifications during generation against a shared database catalog of canonical qualifications. OpenAI selects existing canonical IDs or proposes a new canonical qualification when none fits, for both resumes and jobs. For example, k8s and Kubernetes resolve to the same catalog ID. Preserve original evidence labels separately. Do not infer proficiency, experience, or credentials. Initial requirements have equal weight; matching compares canonical IDs, with no hand-maintained alias map or ranking-time normalization.
- Score all prepared jobs matching the selected titles before limiting results; semantic top-k retrieval must not exclude stronger qualification matches. Read lightweight qualification data in pages.
- Keep resume text and the user’s selected qualification IDs in browser memory only. Persist shared canonical qualification vocabulary, without resume evidence or a user/profile association. Read UTF-8 .txt files in the browser and submit text as JSON. No resume persistence, localStorage, or request-body logging. Explain that extraction sends text to OpenAI.
- Interpret “batch job” as bounded, resumable application batches, not the OpenAI Batch API. No worker queue or durable scheduler in this first implementation.
- Successful extraction with zero qualifications is distinct from failed or pending extraction. Exclude unknown fit from scored results and report preparation coverage.

## 1. Acceptance contracts and schemas

Follow `docs/new-feature-development.md`: write a user-story acceptance test for each slice, implement it, then document usage. Prefer pure functions and injectable providers.

Add bounded schemas: 1–10 titles (200 characters each), 1–100 reviewed skills (200 characters each), 1–20 results, and a maximum 64 KiB UTF-8 resume with an explicit token limit. Reject blank/oversized input before provider calls; do not silently truncate resumes. Empty extraction is a valid response requiring user correction.

| Endpoint | Proposed contract |
| --- | --- |
| GET /jobs/titles?q=...&limit=10 | Bounded distinct title suggestions; case-insensitive matching and deterministic ordering. |
| POST /resume/qualifications | Accept text; resolve extracted qualifications to catalog IDs and labels for review. May extend the shared catalog; persist no resume or personal qualification set. |
| GET /qualifications?q=... | Bounded canonical qualification suggestions for reviewing/editing extracted skills. |
| POST /qualifications/resolve | Resolve user-added qualification labels through the same select-or-augment process; return canonical IDs and labels. |
| POST /jobs/prepare | Accept titles and a validated continuation cursor; process at most 5 pending jobs; return progress, failures, next cursor, and completion. |
| POST /jobs/fit | Accept titles, reviewed canonical qualification IDs, and limit; return ranked jobs, coverage, matched/unmatched requirements, and preparation counts. |

Register literal job routes before /jobs/{job_id}. Title filters use case-insensitive literal substring matching plus PostgreSQL trigram word/whole-title similarity, OR across titles, with SQL wildcard escaping. This allows extended titles and small typos while keeping unrelated titles out. Allow free-text titles without selecting a suggestion. Automatic role taxonomy is deferred.

## 2. Database migration and derived-data lifecycle

Add Alembic revision 0003, preserving current postings:

- Add content TEXT containing the full cleaned title/description document. Reuse the existing HTML-to-text helper; bound provider input separately.
- Add metadata JSONB NOT NULL DEFAULT '{}' containing derived platform/company/location/remote/tags. Map it to a Python attribute such as search_metadata because SQLAlchemy reserves metadata. Existing typed fields remain authoritative.
- Add stored generated fts TSVECTOR using an explicit simple configuration over content, with a GIN index. Add the requested GIN metadata index. These support text/metadata retrieval; they do not calculate skill coverage.
- Reuse embedding VECTOR(1536), add HNSW with vector_ip_ops, and align ordinary semantic-search ordering with negative inner product. Normalize vectors on write/query and bump the embedding version so existing vectors are rebuilt on demand. Fit coverage ranking itself remains exact and does not depend on approximate retrieval.
- Add qualifications(id, canonical_name, normalized_name UNIQUE, merged_into_id NULL) and job_qualifications(job_id, qualification_id, evidence_label), with foreign keys and a unique (job_id, qualification_id) pair. The self-reference merged_into_id preserves redirects after a catalog merge; reject redirect cycles. Canonical IDs are stable. The catalog starts empty and grows through extraction; no synthetic seed vocabulary is required.
- Add a qualification extraction version. Keep legacy qualifications readable, but re-extract unversioned/stale qualifications during preparation.

Backfill content/metadata in bounded pages without API calls. Synchronize both in ingestion. Invalidate qualifications/version and job qualification links on relevant source changes and embedding/version on title/description changes. Commit derived output only if its source fields still match, following the existing atomic embedding-write pattern. Keep internal fields out of public job responses. Preserve the legacy qualifications string list as a compatibility projection of canonical labels, updated atomically with job qualification links. Legacy unversioned lists do not count as prepared canonical data.

The database notes add retrieval infrastructure beyond the core fit story. FTS/metadata indexes are delivered as specified; a new hybrid-ranking algorithm is not needed for this workflow.

Add revision 0004 to enable `pg_trgm` and create a GIN trigram index on titles. Use the
index-backed `<%` and `%` operators for word and whole-title similarity. Keep the literal
predicate first for exact substrings and escape wildcard characters.

## 3. Shared extraction and resumable preparation

Refactor app/agents/job_posting.py into injectable structured extraction with separate resume/job prompts and a shared catalog resolution step during generation. Extract only explicitly evidenced requirements; treat document text as data. Apply bounded timeouts/retries, validated output, and sanitized errors. Release database transactions before provider calls.

Catalog resolution:

1. Extract bounded, evidence-backed qualification phrases, then retrieve a bounded set of existing catalog candidates for each phrase (exact normalized-name lookup plus lexical candidate retrieval). Send candidates to OpenAI with their IDs and names. Never send the entire unbounded catalog.
2. Require structured choices: an existing candidate ID or a proposed concise canonical name. Validate that returned IDs were supplied; reject invented IDs. Let OpenAI resolve synonyms during generation, not during fit ranking. Keep evidence outside the shared catalog.
3. Before inserting a proposed name, retrieve possible equivalents and run the same resolution step when candidates exist. Insert genuinely new names with unique normalized-name constraints and conflict-safe upserts, reusing the winning ID on concurrent identical inserts. Deduplicate returned IDs.
4. Exact-name uniqueness cannot eliminate every concurrently proposed semantic synonym. Provide an explicit transactional catalog-merge helper that repoints job links and deduplicates them; preserve old IDs as redirects so already-reviewed browser selections remain valid. Test this limitation and repair path rather than promising perfect ontology generation.
5. Validate all submitted qualification IDs against the catalog and resolve redirected IDs before ranking. Added user skill labels use the same resolver; text edits cannot bypass canonicalization.

Keep the single-job enrichment endpoint, including force, on the same extraction contract and stale-write protection. Add preparation orchestration around reusable enrichment and embedding helpers.

Freeze an upper job-ID bound on the first preparation request and use a validated cursor tied to the selected titles. Advance after every attempted row, so failures cannot cause infinite retries. Fresh runs retry only missing/stale/failed work; successful committed results are reused. Report failures by internal job ID without document text or raw provider responses.

After optional POST /jobs/scrape, prepare only postings matching the chosen titles. Skip-refresh still prepares stored candidates. Refresh failure offers continuation with stored data. Partial preparation returns usable results with pending/failed counts and a retry action. Jobs with qualifications but failed document embeddings remain rankable by coverage, with deterministic fallback for ties.

## 4. Fit ranking service

Create app/skill_fit.py with pure canonical-ID overlap and scoring functions plus database orchestration. Apply the requested title predicate first, then load canonical requirement IDs only for those candidates and compute coverage against reviewed resume IDs. Limit after qualification ranking. Do not normalize labels or call OpenAI to decide matches during ranking.

Return job details, internal ID, current source URL, coverage fraction/counts, and original matched/unmatched requirement labels. Label unmatched requirements “Not found in your resume,” not assertions that the person lacks them.

Use document embedding similarity for jobs tied at the result boundary, then ID; do not expose it as qualification coverage. If query embedding fails, retain deterministic coverage ordering and indicate the fallback. Return explicit no-match results if all prepared candidates have zero overlap. Distinguish no title candidates, preparation needed, empty resume extraction, and no overlap.

Arbeitnow rename reconciliation is separate scope. Use existing internal IDs for result identity and stored-job links; label external URLs as original postings without promising permanence.

## 5. Main-page workflow

Extend app/static/index.html, search.js, and styles.css within the existing visual style:

1. Enter titles with debounced, keyboard-accessible autocomplete and removable selections.
2. Upload a text resume; extract against the shared catalog and show removable canonical qualification chips. Add skills through catalog suggestions or the shared label resolver; carry canonical IDs through submission.
3. Review skills and choose whether to refresh postings.
4. Submit: optionally scrape -> prepare bounded batches -> retrieve ranked results.
5. Show “3 of 5 extracted requirements evidenced,” matching/not-evidenced labels, and stored/original posting links.

Prevent duplicate submissions, discard stale autocomplete/workflow responses after inputs change, and preserve inputs on failures. Display phase/progress and allow stopping between batches. Retry without repeating successful extraction or enrichment. Use safe text rendering, existing URL validation, accessible status announcements, and clear empty states. Retain free-text search as an alternate mode. No extra LLM answer-generation call for skill-fit results.

## 6. Verification and delivery

- PostgreSQL acceptance tests: data-preserving migration/backfill, generated FTS/index definitions, metadata synchronization, title pre-filtering before preparation/ranking (including an unrelated-title job with perfect skill overlap), strongest-match ordering across filtered candidates, canonical-ID matching, zero/unknown coverage, and stable ties.
- Catalog tests: resume/job synonyms select the same ID, unseen skills extend the catalog, invented IDs are rejected, repeated extraction is idempotent, concurrent identical inserts reuse one row, and catalog merging preserves job links and old submitted IDs. Update isolated database fixture teardown for foreign-key dependencies and added tables.
- Lifecycle/provider tests: extraction failure or empty output, input bounds, invalid vectors, version changes, resumable partial failure, concurrent source updates, and resume non-persistence (only generic catalog vocabulary may persist). Use pure functions/injected providers instead of paid calls.
- API/UI tests: route precedence, autocomplete limits and wildcard escaping, refresh versus skip, reviewed-skill submission, batch progress/retry, stale responses, safe rendering, and empty/error states. Preserve existing search regressions.
- Verify inner-product ordering agrees with normalized cosine ordering and the query operator matches the index; do not require tiny test fixtures to choose an index scan.
- Run make test, node --test tests/*.test.mjs, and configured lint checks. Use the isolated _test database; do not reset development data. Manually verify the complete browser workflow at desktop and narrow widths.
- Update README with workflow, minimal API examples, limits, batch/retry behavior, ranking limitations, and migration/re-embedding steps.

Implementation notes: preparation is capped at five jobs per request. Catalog candidate retrieval sends at most 200 vocabulary entries to the model, ranked lexically; model resolution handles semantic equivalence. Browser visual verification is pending because no browser is connected.

Implementation sequence: acceptance contracts -> migration/catalog/ingestion -> shared extraction and catalog resolution -> preparation -> ranking/API -> page workflow -> regression checks/documentation. Cloud deployment, accounts, PDF/DOCX parsing, and upstream-ID reconciliation are outside this design.
