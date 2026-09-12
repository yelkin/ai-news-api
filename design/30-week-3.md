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
