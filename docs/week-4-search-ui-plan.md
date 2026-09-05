# Week 4 bonus: search UI execution plan

## User story and scope

As a job seeker, I can open the app, describe the work I want, and see relevant job postings with links to their original listings.

Implement the “Week 4 bonus - search UI” section of README.md: a simple Google-style single page backed by the existing POST /jobs/search endpoint. Use an original “Job Search” wordmark with a silly googly-eyed briefcase mascot, generous white space, a rounded search field, blue result links, and muted metadata.

## Proposed experience

1. At GET /, show a centered wordmark and silly mascot, a labeled search field, a Search button, and a short example query. The page works on desktop and mobile.
2. Submit with Enter or the button. Move the search form into a compact top area and display a loading status while the API runs. Preserve the query so it can be edited and searched again.
3. Show the generated answer in a compact “Search summary” section, followed by a simple vertical list of job results. Render the answer as plain text with preserved line breaks; no Markdown library is required. Show cited jobs as separate links derived from cited_job_ids.
4. For each result, display company/source domain, a blue linked job title, location/remote information, and a short plain-text description excerpt. Use source_url for the original posting link. Preserve the jobs array order exactly; the backend already ranks by relevance.
5. Label the count as “N results shown,” since the API does not return a total match count. Display up to 10 results per search. Pagination, filters, autocomplete, and scraping/embedding controls are outside this bonus.
6. For an empty response, show a friendly no-results message with an invitation to try another query. For network/provider errors, show an inline retry message and retain the query. Do not display old results as if they belonged to a failed new query.

## Implementation approach

- Add app/static/index.html, app/static/styles.css, and app/static/search.js. Use plain HTML, CSS, and JavaScript with no frontend framework, build step, remote fonts, or new dependencies.
- Serve the page at GET / and assets under /static from FastAPI using paths resolved relative to the application module. Keep /docs and the existing API routes intact.
- Use same-origin fetch to POST /jobs/search with JSON {"query": "...", "limit": 10}. The browser never calls OpenAI directly. Reference the existing /docs#/default/semantic_search_jobs_search_post operation or the app's /openapi.json in the request code.
- Trim input and reject blank queries; enforce the API's 2,000-character limit. Show a clear pending state and suppress repeated submissions while one request is running. Provide a retry after failures.
- Separate response-to-view-data conversion from network calls and DOM updates. Keep result ordering unchanged and use job IDs to connect citation links to the relevant result.
- Insert untrusted text with textContent. Convert HTML descriptions into plain-text excerpts with a detached parser; never insert posting HTML into the live document. Only make valid absolute HTTP(S) source URLs clickable. If a source URL is missing or invalid, show the result with “Source link unavailable” rather than inventing a destination.
- Use semantic form elements, visible keyboard focus, an accessible input label, and a live status region for loading/error/result counts. Keep result text readable and avoid horizontal scrolling on narrow screens.
- Verify that static files are included in the installed package and Docker image. The existing COPY app command should include them; adjust packaging only if verification shows otherwise.

## Development and verification

Follow docs/new-feature-development.md feature by feature: user story → simplest acceptance test → implementation → passing tests → minimal README example. Put the user story in the route docstring and frontend documentation comments where appropriate. Use standard Unix patch for edits and bubblewrap for local Python/test execution, retaining the established separation between test execution and Docker management.

1. **Page delivery:** First write an acceptance test for GET / returning the search form and the referenced assets being served. Implement the static page and routes; verify /docs and API routes still work.
2. **Search interaction:** Define browser acceptance scenarios before writing the interaction code: submit a query, show loading, display summary and ordered result links, then submit another query. Exercise the actual FastAPI route against the disposable test database with controlled provider functions so routine checks do not call paid APIs. Prefer pure-function checks for data conversion over mocking fetch or HTTP.
3. **Edge states:** Verify blank input, empty results, provider/network failure and retry, repeated submission, missing source URLs, HTML descriptions, and unsafe URL schemes. Ensure supplied markup is displayed only as text and relevance order is preserved.
4. **Visual and keyboard review:** Inspect the page in the available browser tooling at desktop and mobile widths. Check initial, loading, results, empty, and error states; submit by keyboard and follow a job link. Use the browser skill when performing this review. If browser automation requires an unavailable dependency or capability, report that requirement rather than adding a package or bypassing the requested workflow.
5. **Regression and delivery:** Run the existing test suite plus the new page tests inside bubblewrap, check formatting, and verify static asset delivery from the packaged app. Add a short README instruction: run make dev, open http://localhost:8000, and search after scraping and embedding jobs.

## Completion criteria

- Opening / shows the centered search page.
- Submitting a query calls the existing /jobs/search endpoint and presents its summary and job results.
- Results retain backend relevance order and valid titles link to the original postings.
- Loading, empty, and error states work without losing the query.
- The page is usable on mobile and by keyboard, with no additional dependencies.
- Existing API tests and the new acceptance checks pass; desktop/mobile browser review is recorded.

Approved in Plannotator with the request for a silly logo. Implemented with a googly-eyed briefcase mascot. Browser visual and interaction review remains pending because no browser is connected.
