# AI Job search

This test project scrapes job boards and finds the ones best fitting your skills.

## User story lifecycle

### Design
When developing a new feature, put the design under `design/`.

### Development
When writing code, follow the workflow in `docs/new-feature-development.md`.


### Match jobs to your resume (Week 5)

Run `make migrate` and start the application, then open `/` and choose **Match my skills**:

1. Enter up to 10 job titles separated by semicolons. Suggestions come from stored jobs.
2. Upload a UTF-8 `.txt` resume (up to 64 KiB and 12,000 tokens) and extract qualifications.
3. Review the canonical qualification chips. Remove incorrect items or add a qualification.
4. Choose whether to refresh postings, then select **Find matching jobs**.

Resume text is sent to OpenAI for extraction but is not stored by this application. Shared
qualification vocabulary is saved without personal evidence or a resume/profile association.
The model chooses existing canonical qualifications or extends the catalog. Set
`QUALIFICATION_MODEL` to override the existing default `gpt-5.6`.

Jobs are filtered by the selected titles first (literal substring plus PostgreSQL trigram
similarity, OR across titles), then
ranked by the fraction of extracted job qualifications evidenced by your reviewed skills.
All qualifications have equal weight. Canonical IDs match exactly; model normalization
can make mistakes, so review your skills. Document similarity breaks coverage ties only.
“Not found in your resume” does not mean you lack that skill. Scores are not hiring probabilities.

Preparation processes at most five matching jobs per request. Extraction and embedding use
OpenAI and may take several minutes. The page shows progress, supports stopping between steps,
and reuses completed work on retry. Skipping refresh still prepares stored jobs. Partial failures
do not hide jobs with usable qualifications; choose **Retry preparation** to finish missing work.
The workflow does not run in a durable background queue: keep the page open to advance batches.

Minimal API workflow (see `/docs` for full schemas):

```bash
curl 'http://localhost:8000/jobs/titles?q=Reliability'
curl -X POST http://localhost:8000/resume/qualifications \
  -H 'Content-Type: application/json' -d '{"text":"I operate Python services on Kubernetes."}'
curl -X POST http://localhost:8000/jobs/prepare \
  -H 'Content-Type: application/json' -d '{"titles":["Site Reliability Engineer"]}'
# Repeat preparation with its next_cursor until complete; use returned qualification IDs below.
curl -X POST http://localhost:8000/jobs/fit \
  -H 'Content-Type: application/json' \
  -d '{"titles":["Site Reliability Engineer"],"qualification_ids":[1,2],"limit":10}'
```

`GET /qualifications?q=...` suggests catalog entries; `POST /qualifications/resolve` resolves
added labels. Resume/resolve requests accept at most 100 skills, each up to 200 characters.
No-match responses distinguish missing title candidates, preparation needed, and no overlap.
Internal `/jobs/{id}` links identify saved postings; external Arbeitnow links may change or expire.

Migration `0003` preserves postings, backfills cleaned content and JSONB metadata, adds generated
FTS/GIN and HNSW inner-product indexes, and creates the qualification catalog and job links.
Existing qualification lists remain readable but are regenerated into canonical IDs during
preparation. Existing vectors are ignored until rebuilt under the normalized embedding version:
use `POST /jobs/embed` for all jobs, or let skill-fit preparation rebuild selected candidates.
The existing free-text search and job APIs remain available. Catalog synonym repair is available
through the internal `merge_qualifications(session, source_id, target_id)` helper; old IDs redirect.
Migration `0004` enables `pg_trgm` and adds a title trigram index. A title such as
`Site Reliablity Engineer` therefore matches extended titles such as `Senior Site Reliability
Engineer` and `Site Reliability Engineer (m/w/d)`, while unrelated titles remain filtered out.

Validation: `make test` (isolated PostgreSQL database), `node --test tests/*.test.mjs`, and
`uv run ruff format --check app tests migrations`. Automated tests use injected providers, with no paid API calls.
