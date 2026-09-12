## Week 4

The goal for week 4 is to add RAG to the app. The plan is outlined below.

### Prerequisites

- Replace postgres image with pgvector/pgvector:pg17.
- Put the current hard-coded database creation script in an alembic migration.
- Add another migration that adds a vector column to the job posting table
  - Add it to the model as well

### Requirements

- The job posting retrieval workflow should be extended to enrich job postings with vector data:
  - Job posting query endpoint stays as is and queries job postings from Arbeitnow
  - New enrichment endpoint generates vectors from the following data when they're missing:
    - job title
    - job description
- The posting search endpoint should be augmented with a RAG workflow:
  - use pgvector to retrieve relevant postings and send their text along with the query
    to support natural-language search and a grounded answer

### Week 4 database setup

Both Compose databases use `pgvector/pgvector:pg17` (the published PostgreSQL 17 tag).
The initial Alembic migration carries over the previous initialization SQL; the second enables
pgvector and adds a nullable 1,536-dimensional embedding and version field.

```bash
make migrate
```

If switching from the old Alpine image fails due to an incompatible development cluster,
the development data is disposable. To reset this project's Compose databases and volume:

```bash
docker compose down --volumes
make dev
```

This deletes stored development jobs; scrape them again afterward. Tests use only the separate
`TEST_DATABASE_URL`, whose database name must end in `_test`, and apply migrations themselves.


### Embed job postings in bulk

After scraping, generate embeddings for every posting that has no compatible vector:

```bash
curl -X POST "http://localhost:8000/jobs/embed"
# Limit this request to 100 jobs:
curl -X POST "http://localhost:8000/jobs/embed?max_jobs=100"
```

The response reports `selected`, `embedded`, `failed`, `skipped`, and `errors`. A completed request
returns HTTP 200 even with partial failures; inspect `failed` and retry the same request to process
remaining jobs. Successful batches are saved incrementally. `skipped` counts jobs changed or already
embedded by another request while the provider was running. Up to 100 batch errors are included.

This is synchronous bulk processing through the embeddings endpoint, using multiple inputs per
provider request. Jobs are selected in ID order, excluding jobs inserted after the request starts.
Each request contains at most 64 jobs and 16,000 tokens. Existing compatible vectors are cached;
changes to a posting's title or description invalidate its vector during the next scrape.

Embeddings use `text-embedding-3-small`, 1,536 dimensions, and the version defined in
`app/embedding_config.py`. Changing the model, dimension, or text preparation requires coordinated
migration/re-embedding. HTML is normalized; titles are capped at 512 tokens and title plus description
at 8,000 tokens using tiktoken. The remaining description is truncated. The tokenizer may download its
standard encoding data on first use. Vectors are internal and are not returned by job endpoints.

### Search jobs with RAG

Describe the work you want to do after generating job embeddings:

```bash
curl -X POST "http://localhost:8000/jobs/search" \
  -H "Content-Type: application/json" \
  -d '{"query":"Work on reliable backend services using Python", "limit":5}'
```

The response contains `jobs` ranked by cosine distance, an `answer`, and `cited_job_ids` referring
to the returned jobs. Optional `title`, `company`, and `tag` filters narrow the candidates before
ranking and limiting. Queries must be nonblank and at most 2,000 characters; `limit` is 1–20.
Existing `GET /jobs` substring search and qualification enrichment remain available.

Search embeds the query, retrieves compatible vectors from Postgres, and sends the matching job
text to the same `gpt-5.6` model used for qualification extraction. Raw vectors are not sent to the
answer model. Missing/incompatible embeddings are excluded. Empty candidate sets return an empty
job list without calling OpenAI. Provider or citation-validation failures return HTTP 502.

The answer uses bounded excerpts (up to 12,000 tokens of source context), so it may lack details
present in the full jobs returned alongside it. Similarity does not guarantee a suitable job;
the answer can state that the sources do not establish a match. No distance cutoff or approximate
index is applied in this first version.

Bulk embedding runs synchronously. Use `max_jobs` to keep requests small when running behind a
proxy with a request timeout. The Docker worker timeout is disabled to allow long embedding runs;
each provider request still has a 60-second timeout and at most two retries.

### Week 4 bonus - search UI

Implement a simple google main page style single-page UI that invokes the /jobs/search endpoint
and shows the result as a google style result page with links leading to job postings,
ordered by relevance
Open the search page at **http://localhost:8000/** after running `make dev`.
The UI is served by FastAPI and needs no separate frontend installation.

Scrape and embed jobs first (see the commands above), then describe the work you want and press
Enter or **Search**. Results stay in relevance order, with links to the original postings and a
short search summary. Searches show up to 10 jobs. The page supports loading, empty, and retry states;
posting links that are missing or invalid are labeled unavailable.

JavaScript data checks can also be run with an existing Node.js installation:

```bash
node --test tests/search_ui.test.mjs
```
