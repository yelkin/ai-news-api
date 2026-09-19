# AI Job search

This test project scrapes job boards and finds the ones best fitting your skills.

## Run the tests

The test target starts a dedicated PostgreSQL container and runs the suite:

```bash
make test
```

The primary resume-to-job fit integration test also calls the real OpenAI API.
Set `OPENAI_API_KEY` to run it; otherwise pytest skips it. To run only that test:

```bash
make test TEST_RUNNER='uv run pytest -m external_integration'
```

See [the integration-test use case](docs/test-coverage.md) for its scope and
fixture data.
