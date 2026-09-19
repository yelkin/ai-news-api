# Debug toolbar

The search page has a **Debug toolbar** button fixed at the bottom right. Open it
to inspect every application HTTP exchange made since the page was loaded,
including title suggestions, resume qualification extraction, qualification
resolution, fit matching, and free-text search.

Each entry shows the raw method, URL, headers, request body, response status,
response headers, and response body. Network failures are retained with their
error message. Entries stay in chronological order when the popup is closed and
reopened.

The history exists only in browser memory and resets on reload or navigation. It
can include sensitive resume text, so use it only for development and avoid
sharing screenshots or copied payloads containing personal information.
