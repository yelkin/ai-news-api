# Test coverage

## User story

As a job seeker, I can specify a desired job title and upload my resume, then see
similar-title jobs ranked by how relevant their required qualifications are to
my core competencies.

## Acceptance scenario

Given a database loaded from `tests/fixtures/job_postings.json` with Python
Engineer, Site Reliability Engineer, and Senior Site Reliability Engineer
postings, when the job seeker:

1. specifies `Site Reliability Engineer`,
2. submits test resume text for qualification extraction,
3. prepares the similar-title postings, and
4. requests fit results using the extracted qualification IDs,

the API excludes the Python Engineer, includes both SRE variants, and ranks them
by qualification relevance to the resume.

The integration test exercises the HTTP endpoints, real PostgreSQL database,
and real OpenAI API together. Only job data and resume contents are fixtures;
populating the job database through scraping or ingestion is out of scope.

## Implementation plan

1. Add `tests/fixtures/job_postings.json` containing representative Python
   Engineer, Site Reliability Engineer, and Senior Site Reliability Engineer
   postings with qualifications that yield a meaningful ranking.
2. Add one integration test that loads those postings directly into the test
   database, verifies title similarity, extracts competencies from test resume
   text, prepares matching postings, and verifies fit ranking through the API.
3. Call the real OpenAI qualification and embedding providers. Mark the test as
   an external integration test and skip it with a clear reason when the required
   OpenAI credentials are absent, keeping the normal local suite usable.
4. Document the tested user workflow, prerequisites, and focused test command.
5. Run the focused external integration test when credentials are available and
   run the normal full test suite.
