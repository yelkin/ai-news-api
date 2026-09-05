# New feature development procedure

1. Formulate the user story. What concrete user-facing results do you need to get?
2. Follow ATDD approach.
    2.1 Write a simplest acceptance test
        - Don't mock apis or http requests when possible, create functions without side effects instead
    2.2 Implement the required code
        - Put the user story description in the docstring
        - When calling external apis - put a link to the docs/openapi schema
    2.3 Make tests pass
    2.4 Document the feature for the end users in the readme
        - keep it simple
        - include a minimal usage example
    2.5 Continue to the next feature
