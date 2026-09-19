---
name: new-feature-development
description: Develop new features in this repository with user-story-driven acceptance tests, implementation, and concise end-user documentation. Use when adding or extending user-visible behavior.
---

# New feature development

## Design
Start by formulating the user story in terms of the concrete, user-facing result.

1. Write a feature design and implementation plan in `design/N-<feature>.md`.
2. Review it with the developer using `plannotator` skill. Fix all the notes and proceed to implementation.

## Implementation
Use an acceptance-test-driven development loop for each feature slice:

1. Write the simplest acceptance test that demonstrates the user story.
   - Prefer extracting side-effect-free functions over mocking APIs or HTTP requests when practical.
2. Implement only the code required for that behavior.
   - Put the user story description in the relevant docstring.
   - When calling an external API, include a link to its documentation or OpenAPI schema near the integration code.
3. Run the relevant tests and make them pass.
4. Check that the developer ducumentation on how to run the app in `README.md` is up to date and update it.
5. Document the feature for end users in `docs/<feature>.md`.
   - Keep the explanation concise. Only explain the use case you are implementing.
6. Continue with the next independently testable slice.
