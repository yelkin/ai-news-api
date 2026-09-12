## Week 5

Develop the full usable workflow: extract skills from my resume, extract skills from job postings,
show me the ones matching my skills the best.

### User story

1. As a user I open the main page.
2. I enter the job title(s) I'm interested in, e.g. "Site Reliablity Engineer" - there's autocomplete
from existing job postings.
2. I upload my resume in text format. The app queries openAI to extract the core qualifications from it.
3. The page triggers the batch job to fetch job postings (option for the user to skip).
4. The page queries the service for the jobs with the best matching qualifications.

### Database notes

- Augment `job_postings` table
    - fields
        - content: Text field for storing document content
        - metadata: JSON field for flexible metadata storage
        - embedding: Vector column configured for 1536-dimensional vectors (matching OpenAI's embedding dimensions)
        - fts: Auto-generated full-text search vector using PostgreSQL's to_tsvector function
    - indexes
        - HNSW Index on embeddings: Uses vector_ip_ops (inner product) for fast similarity search. We chose HNSW over IVFFlat for better recall and query performance
        - GIN Index on FTS: Enables efficient full-text search queries
        - GIN Index on metadata: Allows fast filtering on JSON fields
