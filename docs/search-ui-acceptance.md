# Search UI acceptance scenarios

- Open `/`: see the googly-eyed briefcase, labeled query field, and search button; assets and `/docs` load.
- Enter a nonblank query and submit by Enter: one POST to `/jobs/search` contains the trimmed query and limit 10; loading is announced, repeat submission is disabled, and the form remains visible.
- Receive results: show the summary and citation links, preserve the API's job order, and link each valid title to its original posting. Show company, location/remote, and a plain-text excerpt.
- Search again: clear previous results during loading and show only the new response. Preserve the submitted query on errors and support Retry.
- Reject whitespace-only and overlong input without a network request.
- Empty results show a friendly message. HTTP or network failures show a friendly retry state rather than stale jobs or raw server details.
- Display supplied HTML as text; ignore script/style content in excerpts. Reject javascript/data/relative/malformed links; retain jobs without valid links and label them clearly.
- At mobile and desktop widths, inspect all states, horizontal overflow, focus visibility, keyboard submission, and a result link.

Browser verification requires an available browser connection; the current browser runtime reports none. Pure transformation tests and server acceptance tests remain runnable without adding dependencies.

## Verification results

- 33 Python acceptance/regression tests passed inside bubblewrap, including page/asset delivery and static file boundaries.
- JavaScript assertions passed for query validation, unsafe links, relevance ordering, citation association, and malformed responses using the available JavaScript runtime.
- Python correctness/import checks passed; no dependencies were added.
- Browser visual and end-to-end interaction checks remain pending: browser discovery returned no available connections.
- A wheel build remains unverified: the declared Hatchling backend is not installed in the application environment, and an offline build via the existing Snap uv command failed inside bubblewrap with a DBus transient-scope error. Source asset delivery is verified; Docker already copies the app/static directory via COPY app.
