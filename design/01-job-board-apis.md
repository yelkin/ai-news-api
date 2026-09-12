# ADR-001: Select public job-board APIs

- Status: Accepted
- Date: 2026-08-22

## Context

The Week 2 brief requires the project to select job sources, retrieve job postings, normalize them, and use AI to distill their key `qualifications`. A useful source must therefore provide current IT jobs with enough title and description text to populate `JobPosting`:

- `platform`
- `company`
- `title`
- `description`
- `tags`
- `qualifications` (derived by the enrichment agent)

This ADR treats an API as **public** when an individual developer can read published jobs without becoming a commercial integration partner. An API key obtained through ordinary developer registration is acceptable but less desirable than anonymous access. Publishing and applicant-tracking APIs do not satisfy the requirement when they cannot search or retrieve public jobs.

## Options considered

| Source | Public read access | Coverage and payload | Constraints | Decision |
|---|---|---|---|---|
| Arbeitnow | Yes; no API key | Aggregated European and UK jobs, including title, company, description, tags, and remote status | Paginated feed; filtering may need to happen locally | **Use now.** It already maps cleanly to `JobPosting`. [API documentation](https://www.arbeitnow.com/blog/job-board-api) |
| Hacker News / Y Combinator | Yes; no authentication | Up to 200 recent job stories through `/v0/jobstories`; item records include title, HTML text, and optional URL | Sparse and inconsistent fields; company and tags often require extraction | **Use now.** Good source of startup IT roles and already represented in the exploratory script. [Official HN API](https://github.com/HackerNews/API) |
| Greenhouse Job Board | Yes; GET endpoints need no authentication | Published jobs for a specified employer; `content=true` supplies the full description | Requires a curated employer board token; not a global job search | **Add next.** High-quality descriptions are well suited to qualification extraction. [Job Board API](https://developer.greenhouse.io/job-board.html) |
| Lever Postings | Yes for published postings | Published jobs for a specified employer, with HTML and plain-text descriptions plus categorized lists | Requires a curated employer site name; no full-text search across employers | **Add next.** Plain-text descriptions and requirement lists map well to the model. [Official Postings API](https://github.com/lever/postings-api) |
| Ashby Job Postings | Yes for an organization's public board | Published jobs, description, location, URLs, and optional compensation | Requires a curated job-board name; no global search | **Add next.** Particularly useful for technology/startup employers. [Job Postings API](https://developers.ashbyhq.com/docs/public-job-posting-api) |
| Remotive | Yes; no API key | Remote jobs with company, title, category, full HTML description, location, and salary | Jobs are delayed by 24 hours; attribution and backlinks are required; recommended maximum is four requests per day | **Optional phase 2.** Use only with source attribution and conservative caching. [Public API documentation](https://github.com/remotive-io/remote-jobs-api) |
| Remote OK | Yes; JSON feed | Remote job listings from a technology-focused board | Attribution and links to original postings are required; response/terms should be rechecked before implementation | **Optional phase 2.** Useful for remote IT coverage after attribution is designed. [API help](https://remoteok.featurebase.app/help/articles/3140840-is-there-an-api-or-rssjson-feed-of-remote-jobs) |
| USAJOBS | Yes after ordinary API-key registration | Searchable US government jobs, including IT occupational series | Requires an API key and request headers; government-only coverage | **Optional specialist source.** Add if US public-sector roles are in scope. [API reference](https://developer.usajobs.gov/api-reference/) |
| LinkedIn | No open job-search API | Talent APIs can create and manage LinkedIn postings | Access is restricted to approved LinkedIn Talent Solutions partners under an API agreement | **Do not integrate for Week 2.** [LinkedIn Job Posting API requirements](https://learn.microsoft.com/en-us/linkedin/talent/apply-connect/create-apply-connect-jobs) |
| Indeed | No open job-search API | Current Job Sync API creates and manages an integration owner's postings | Requires a developer agreement, partner approval, integration review, and OAuth credentials; it is not a public search feed | **Do not integrate for Week 2.** [Indeed integration guide](https://docs.indeed.com/job-sync-api/integrate-with-job-sync-api) |
| Stack Overflow Jobs | No independent public listings API | The current Stack Overflow Jobs experience is powered by Indeed | Inherits Indeed's lack of an open search API; Stack Overflow exposes no documented independent jobs feed | **Do not integrate.** Treat it as an Indeed discovery surface, not a source API. [Stack Overflow–Indeed announcement](https://stackoverflow.co/company/press/archive/indeed-partnership) |

## Decision

Use a staged source strategy:

1. Keep **Arbeitnow** as the first end-to-end source because it is anonymous, aggregated, and already implemented.
2. Add **Hacker News Jobs** as the second global/startup source.
3. Implement a reusable employer-board connector pattern for **Greenhouse**, **Lever**, and **Ashby**, driven by configured board identifiers.
4. Consider **Remotive** and **Remote OK** only after the output includes source URLs/attribution and the scheduler can enforce their usage terms.
5. Defer **USAJOBS** until public-sector coverage is explicitly required.
6. Exclude **LinkedIn**, **Indeed**, and **Stack Overflow Jobs** from scraping/API ingestion. Do not work around their access models with undocumented endpoints or HTML scraping.

Every scraper should return one or more normalized `JobPosting` objects. The enrichment step should preserve source facts and populate `qualifications` with short phrases derived from the description. Raw and enriched results should be serializable into the Week 2 `output/` directory when that persistence step is implemented.

## Consequences

### Positive

- The first sources require no credentials and can be exercised interactively in VS Code/Jupyter.
- Full descriptions from Arbeitnow and ATS boards give the enrichment model useful qualification evidence.
- Employer-scoped adapters share a simple configuration pattern and avoid brittle HTML scraping.
- The decision respects documented access and attribution requirements.

### Negative

- LinkedIn and Indeed, despite their coverage, cannot be used as open discovery APIs.
- Greenhouse, Lever, and Ashby need curated employer identifiers and therefore do not provide global search by themselves.
- Hacker News fields are inconsistent and may require AI-assisted company/tag extraction.
- Remote feeds introduce attribution, caching, and freshness obligations.

## Implementation notes

- Return `list[JobPosting]` from multi-result scrapers; let the pipeline select or enrich records explicitly.
- Preserve the original posting URL in the schema before adding sources whose terms require backlinks.
- Store per-source request limits and board identifiers as configuration rather than hard-coding them in scraper logic.
- Keep HTTP collection deterministic; use the OpenAI enrichment step only for semantic normalization such as `qualifications`.
- Record source, retrieval timestamp, and source job ID before persistence so scheduled runs can deduplicate postings.
