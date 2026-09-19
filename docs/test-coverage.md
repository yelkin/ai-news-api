# Resume-to-job fit integration test

The primary user journey starts with a desired job title and resume text. The
service finds stored postings with similar titles, extracts core competencies
from the resume and job descriptions, and ranks those jobs by qualification fit.

`tests/test_user_journey_integration.py` covers that journey using three fixture
postings. It loads the fixtures directly because job ingestion is a separate
feature. The test uses the real PostgreSQL database and OpenAI API.

Set `OPENAI_API_KEY`, start the test database, and run:

```bash
make test TEST_RUNNER='uv run pytest -m external_integration'
```

Without `OPENAI_API_KEY`, the external integration test is skipped.
