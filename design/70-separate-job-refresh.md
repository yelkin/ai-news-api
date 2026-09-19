# Separate job refresh and preprocessing

## User stories

### Search

As a job seeker, I can search prepared postings without waiting for scraping or
job preprocessing. If matching postings still need preparation, I am told that
job data must be updated and can navigate to the update page.

### Job data maintenance

As the person maintaining job data, I can open a dedicated page, refresh stored
job postings, and preprocess postings for selected job titles while seeing
progress and failures. Completed batches are retained, so I can stop or retry
without repeating successful work.

## Acceptance scenarios

1. The search page contains title and resume controls but no refresh checkbox or
   preprocessing workflow. Selecting a valid resume file automatically extracts
   and displays its qualifications; there is no separate extraction action.
   Finding matches calls `/jobs/fit` directly.
2. If `/jobs/fit` reports pending or failed preprocessing, the search page links
   to the job-data page instead of starting preparation itself.
3. The job-data page is available at `/jobs/manage`, is linked from the search
   page, and lets the maintainer enter up to ten titles.
4. Starting an update calls `/jobs/scrape` once and then `/jobs/prepare` in
   resumable batches until complete. The page reports processed and failed
   counts and supports stopping between batches and retrying.
5. Refresh and preparation failures are surfaced without discarding completed
   work.

## Implementation plan

1. Add a server route and static HTML page for `/jobs/manage`, with shared
   branding, navigation back to search, title suggestions, progress, stop, and
   retry controls.
2. Extract reusable title parsing and the resumable preparation loop into a
   small browser module shared by both page scripts where useful.
3. Remove scrape/preparation controls and requests from the skills search page;
   trigger qualification extraction when the resume file is selected, call fit
   directly, and point incomplete-data states to `/jobs/manage`.
4. Add JavaScript acceptance tests for both page workflows and HTTP integration
   tests for the new page, assets, navigation, and accessible controls.
5. Update end-user documentation and README instructions, then run JavaScript
   and Python test suites.
