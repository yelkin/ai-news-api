# Debug toolbar

## User story

As a developer debugging the search page, I can open a debug toolbar and inspect
the complete raw HTTP request and response history generated since the current
page load, so I can understand the app's client/server interactions without
opening browser developer tools.

## Acceptance scenarios

1. A fixed **Debug toolbar** button appears at the bottom right of the search
   page without obscuring the primary search controls.
2. Activating the button opens an accessible popup containing every HTTP call
   made by the search-page workflows during the current page session, ordered
   from oldest to newest.
3. Each successful entry shows the raw request method, URL, headers and body,
   followed by the raw response status, headers and body.
4. Failed requests remain visible with their request data and network error.
5. Opening and closing the popup does not clear the history. Reloading or
   navigating away starts a new in-memory session; debug data is never persisted
   or sent anywhere beyond the original application requests.
6. Raw values are rendered as text rather than HTML, so job data, errors, and
   resume contents cannot inject markup into the page.

## Implementation plan

1. Add a shared browser HTTP wrapper that records request, response, and failure
   details in memory and notifies the toolbar when entries change.
2. Route all search-page fetches—free-text search, title and qualification
   suggestions, resume extraction, qualification resolution, and fit search—
   through the wrapper.
3. Add the fixed button and accessible dialog markup to the search page, plus a
   small module that renders the chronological history and handles open/close.
4. Style the popup for readable raw payloads on desktop and mobile while keeping
   the debug trigger visually distinct from application actions.
5. Add browser-unit tests for successful and failed request capture and HTTP/UI
   acceptance tests for the toolbar controls and assets.
6. Add concise developer documentation and run the JavaScript and Python suites.
