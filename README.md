# AI News

An AI news platform that collects and standardizes news into PostgreSQL, exposes structured news
through API and also chunks and embeds article content so users can semantically search or ask
questions over the news using RAG.

## Design

```mermaid
flowchart LR
    A["Sources"] --> B["Scraper"]
    B --> C["AI Processing"]
    C --> D["Database"]
    D --> E["API"]
    E --> F["Consumers"]

    S["Scheduler"] -.-> B
    G["Config & Secrets"] -.-> C
    G -.-> E
    H["Deployment"] -.-> D
    H -.-> E
    H -.-> S
```

Tech Stack
- Python
- Pydantic
- OpenAI API
- FastAPI
- SQLAlchemy
- PostgreSQL
- Docker
- uv
- Render

## Week 2 - Build a news scraping API

### Brief
Todays goals:
- Define which news I wanna scrape.
- Find sources to scrape. Find their APIs.
- Define what stuff will AI analyze.
    - Define the data model
- Write a scraper script I can run interactively with vscode jupyter intergration
    - save articles into 'output/' directory

### Goal
Scrape job posting boards for relevant jobs and distill the key `qualifications` they require.

## Week 3

We are using the Arbeitnow query code from week 2 and adding API and storage to scrape job postings and
store them in PostgreSQL, and an API to query results.

### Setup

Create the local environment file and add a valid OpenAI API key:

```bash
cp .env.example .env
uv sync
```

The required configuration is:

- `OPENAI_API_KEY`: used to extract qualifications from each posting.
- `DATABASE_URL`: a SQLAlchemy PostgreSQL URL using the installed Psycopg driver, for example
  `postgresql+psycopg://ainews:ainews@localhost:5432/ainews`.
- `TEST_DATABASE_URL`: the dedicated PostgreSQL test database URL. The example configuration points
  to the disposable `postgres-test` Compose service on port 5433.

Start PostgreSQL and the FastAPI application together:

```bash
make dev
```

PostgreSQL runs through Docker Compose with a named `postgres_data` volume. FastAPI runs at
`http://localhost:8000`; its OpenAPI documentation is available at `http://localhost:8000/docs`.
Alembic migrations run before the application starts via `make dev`. Run `make migrate` to upgrade
the schema separately. For deployments, run `uv run alembic upgrade head` before starting workers;
the Docker image includes the migrations. Application startup no longer changes the schema.

### Scrape jobs

Fetch and store the complete Arbeitnow board without calling OpenAI:

```bash
curl -X POST "http://localhost:8000/jobs/scrape"
```

During development, `max_pages` can limit collection:

```bash
curl -X POST "http://localhost:8000/jobs/scrape?max_pages=5"
```

The response reports the number of collected, inserted, updated, unchanged, and failed postings.
Repeated scrapes update matching `(platform, source_job_id)` records rather than creating duplicates.
OpenAI is not called during collection.

### Query jobs

List stored jobs:

```bash
curl "http://localhost:8000/jobs"
```

Search title, company, description, location, and tags in PostgreSQL:

```bash
curl "http://localhost:8000/jobs?search=reliability&offset=0&limit=20"
```

The `title`, `company`, and `tag` parameters provide additional field-specific filtering. All filters
are applied before pagination.

Retrieve one posting by its database ID:

```bash
curl "http://localhost:8000/jobs/1"
```

New postings have `qualifications: null` until enrichment is requested. Extract and cache a posting's
qualifications with:

```bash
curl -X POST "http://localhost:8000/jobs/1/enrich"
```

Subsequent requests return the cached enrichment without calling OpenAI. Regenerate it explicitly
with:

```bash
curl -X POST "http://localhost:8000/jobs/1/enrich?force=true"
```

Check API and database readiness:

```bash
curl "http://localhost:8000/health"
```

Run the automated tests with:

```bash
make test
```

The test target starts a separate PostgreSQL container backed by temporary storage. Tests recreate
tables only in `TEST_DATABASE_URL`; they do not modify the persistent development database.


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
