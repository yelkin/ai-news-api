# Week 4 execution plan: pgvector and RAG

## Goal and API contract

Implement README Week 4 using the existing job-posting application. POST /jobs/scrape fetches Arbeitnow data; GET /jobs searches stored data. Preserve these endpoints and the current qualification-enrichment endpoint.

Vectors select matching rows; the generation model receives the retrieved job text, IDs, and URLs together with the user's question. Semantic retrieval supplies ranked jobs; the subsequent grounded answer supplies the generation part of RAG.

## Development procedure

Follow docs/new-feature-development.md for each feature: formulate a concrete user story, write the simplest acceptance test first, implement, make tests pass, and add a minimal README usage example before continuing. Put user stories in docstrings and link external API documentation at call sites. Prefer pure functions and real local database integration over mocking APIs or HTTP requests where practical.

Proposed contract for review:
- POST /jobs/embed generates all missing embeddings from title and description, with optional positive max_jobs query parameter (for example POST /jobs/embed?max_jobs=100). Process jobs in deterministic ID order and return counts of selected, embedded, failed, and stale/skipped jobs plus useful failure details. Existing compatible embeddings are not regenerated. A per-job endpoint is optional manual debugging support only.
- POST /jobs/search accepts a query, bounded result limit, and optional title/company/tag filters. Return ranked jobs, a grounded answer, and cited job IDs.
- Keep GET /jobs and its existing substring search, filters, and pagination compatible. This new endpoint provides the semantic search mode.
- Exclude postings without compatible embeddings. With no candidates, return empty results and a fixed no-matches answer without calling generation.
- Bulk processing is the primary feature: use bounded multi-input embedding requests and incremental database commits, keeping memory and provider token limits bounded. Start with one vector per posting and synchronous execution; queues, chunking, and approximate indexes are deferred.

## 1. Database runtime and migrations

1. Verify the README's pgvector/pgvector:17 image tag exists and select the published PostgreSQL 17 tag if it differs. Switch both development and test Compose services.
2. Check compatibility when switching the development image. If the existing cluster is incompatible, recreate the disposable development database; preserving its data is not required. Document the reset and limit it to this project’s development database.
3. Use the already-added Alembic, pgvector, and tiktoken dependencies. Preserve the user's existing edits. If another dependency is required, report that need rather than installing it or working around its absence.
4. Add Alembic configuration using DATABASE_URL and SQLModel metadata. Move the current database initialization behavior into the initial migration, including nullable qualifications, enrichment tracking, indexes, and source uniqueness. Raw SQL is acceptable where it simplifies this; keep the migration self-contained rather than depending on future mutable model definitions.
5. Keep initial setup simple: support a fresh development database and use conditional DDL where needed to carry over the existing initialization behavior. A comprehensive legacy adoption or data-preservation workflow is not required; reset the development database if needed.
6. Add a second revision enabling the vector extension and adding a nullable fixed-dimension vector column plus embedding model/version metadata. Choose and document the embedding model and dimension before writing this revision. Downgrade removes new columns without dropping a potentially shared extension.
7. Remove create_all and ad hoc ALTER TABLE from FastAPI startup. Add a migration command, run upgrade head before local app startup, and document deployment migration execution.
8. Update test setup to exercise migrations against TEST_DATABASE_URL, retaining isolation from development data.

## 2. Embedding service and lifecycle

1. Add a small embedding service separate from qualification extraction. Build deterministic text from labeled title and description, consistently normalizing HTML.
2. Use the same embedding model and dimensions for postings and queries. Use tiktoken to bound individual inputs and aggregate batch tokens; define truncation for oversized descriptions, retaining the title, and document this limitation.
3. Implement bulk selection of missing embeddings, respecting max_jobs across the whole request. Map provider response indexes back to job IDs and validate dimensions. Commit successful batches incrementally; report failed batches/jobs and leave them retryable. A subsequent request processes remaining missing embeddings. An empty selection returns a zero-count summary without provider calls; existing compatible embeddings are untouched.
4. Before saving a provider result, verify that title/description still match the input snapshot; concurrent scraping must not install a stale vector. Avoid row locks during provider calls.
5. In ingest_jobs, invalidate embeddings when title or description changes. Preserve them for unchanged postings and unrelated field changes. Retain current qualification invalidation behavior.
6. Separate public response schemas from internal vector fields so existing JSON responses and qualification prompts do not include embeddings or internal metadata.

## 3. Retrieval and grounded generation

1. Embed the query, then order compatible non-null vectors by cosine distance. Apply filters before limiting, with ID as a deterministic tie breaker.
2. Begin with exact vector search. Add an approximate index only when corpus size and measured latency justify it.
3. Bound query length, candidate count, and total retrieved text. Include source IDs and URLs in the context sent to generation.
4. Prompt the model to use retrieved postings as evidence, distinguish missing information, cite job IDs, and treat source content as data rather than instructions.
5. Parse the answer and cited IDs into a structured schema; verify citations belong to retrieved results. Return ranked database records separately from generated text.
6. Similarity does not establish relevance. Inspect representative results before selecting any distance cutoff; do not label distance as calibrated confidence. Allow an answer that the retrieved postings do not establish a match.
7. Return explicit provider errors. Search must not mutate stored postings.

## 4. Validation and documentation

- Migration acceptance tests on disposable Postgres: fresh upgrade, repeated upgrade, vector persistence, and second-revision downgrade/re-upgrade.
- Bulk embedding acceptance test first: multiple missing postings are embedded, existing vectors remain unchanged, and max_jobs limits work. Test pure input/token-budget/batch-planning functions directly; use a minimal controlled provider boundary for deterministic orchestration tests. Cover empty selection, multi-batch processing, response mapping, partial failure/retry, oversized input, and stale-result rejection.
- Ingestion tests: relevant edits invalidate vectors, unrelated edits preserve vectors, and scraping never calls OpenAI.
- Search tests with deterministic vectors: ranking, filters before limit, missing/incompatible embeddings, empty corpus, response contract, source-ID validation, and provider failures.
- Regression coverage for listing, scraping, and qualification enrichment; verify vectors are absent from public responses and qualification prompts.
- Run make test with the pgvector test service and applicable lint checks. Automated tests must not use live OpenAI or development data.
- Document migration/reset commands, embedding configuration, endpoint examples, and how existing postings acquire embeddings.
- If credentials are available during implementation, smoke-test a small sample with real embeddings and paraphrased queries. Report separately if this cannot be performed.

## Delivery order and completion criteria

Implement in stages: runtime/migrations, bulk embedding lifecycle, then search/RAG. Apply the acceptance-test → implementation → passing tests → README cycle within each feature, rather than postponing tests and documentation to the end.

Complete when a fresh development database reaches Alembic head; bulk embedding processes all missing jobs or the requested maximum and supports retries; vectors are invalidated correctly; natural-language search returns ranked stored jobs and a grounded answer; and existing endpoints pass regression tests.

Approved in Plannotator and implemented. Runtime migrations, bulk embedding, source invalidation, semantic search, and grounded answers are covered by acceptance tests. A live smoke test embedded three Arbeitnow postings and verified two queries against the disposable test database. Python tests run inside bubblewrap; development data was not modified.
