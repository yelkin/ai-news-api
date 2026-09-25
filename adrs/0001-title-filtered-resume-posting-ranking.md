# ADR 0001: Rank title-matched jobs with grounded AI comparison

Status: Accepted

## Context

`fit_jobs` filters PostgreSQL postings by requested title, then ranks overlap between AI-extracted resume qualifications and stored `job_qualifications`. Narrow or inconsistent extracted labels can hide relevant evidence in the resume and posting. Whole-posting embeddings only break exact overlap ties. The previous proposal asked OpenAI to categorize each posting separately, but that still leaves many ties and weak comparisons between postings.

Research supports comparing richer evidence, with care. [Vanetik and Kogan (2023)](https://www.mdpi.com/2078-2489/14/8/468) tested full vacancy text and keyword-enhanced representations for resume–vacancy ranking; the best text representation varied, so extracted labels should not be trusted as the sole signal. [Sun et al. (2023)](https://aclanthology.org/2023.emnlp-main.923/) found that instructed LLMs can rerank retrieved passages, using sliding windows when candidates exceed a prompt. These results do not establish accuracy for this app's job matches.

## Decision

Keep the PostgreSQL title filter. Retrieve each candidate's ID, title, **full cleaned description**, and stored `job_qualifications`; do not require qualification overlap to enter the candidate set. Send the user's resume and a token-bounded group of these postings to OpenAI for **listwise ranking**. Ask for an ordered list of the supplied job IDs, a fit category for each, and brief resume/posting evidence for strengths and important gaps. Treat `job_qualifications` as hints to check against the full text, never as facts that override it. Validate that the response contains only the supplied IDs.

For more candidates than fit in one prompt, use overlapping ranking windows rather than truncating the candidate set; split an overlong posting explicitly so its requirements are not silently dropped. Return the highest-ranked postings and their grounded evidence. Replace the old overlap percentage in the fit response and UI with the category and explanation; do not present an AI ranking as a hiring probability. Keep resume text in request memory only. This changes the ranker and its response, with no new database index or embedding model.

## Tradeoffs and verification

Full descriptions preserve context missed by labels, but increase token cost and can bury evidence in long prompts; [Liu et al. (2024)](https://aclanthology.org/2024.tacl-1.9/) document this long-context limitation. Listwise calls are slower and their output can vary. [Vaishampayan et al. (2025)](https://aclanthology.org/2025.findings-naacl.270/) found only minor correlation between GPT-4 and human resume-match ratings, so human evaluation is essential.

Before implementation, compare three top-10 rankings on the same human-judged resume–posting pairs: current qualification overlap, listwise full text, and listwise full text plus qualification hints. Record graded nDCG@10, unsupported evidence, missed requirements, latency, and token cost. Choose the hybrid recommendation only if it improves the judged ranking; otherwise use the better-performing variant. [Kekäläinen and Järvelin (2002)](https://doi.org/10.1002/asi.10137) support graded relevance evaluation for ranked retrieval.
