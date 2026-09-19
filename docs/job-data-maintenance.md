# Updating job data

Job refresh and preprocessing live on the dedicated **Update job data** page at
`/jobs/manage`. Enter one or more job titles, then choose **Refresh and prepare
jobs**. The page fetches current postings once and prepares matching stored jobs
in resumable batches.

You can stop after the active batch and resume later. Successful batches remain
saved, and the status reports refresh and preparation failures separately.

The search page never starts these potentially long-running operations. It uses
the prepared postings immediately and links to the update page when matching
data still needs preprocessing.
