from openai import OpenAI

from app.schemas.models import JobPosting, JobPostingEnrichment, JobPostingRead


def enrich_job_posting(job_posting: JobPosting) -> JobPosting:
    # https://developers.openai.com/api/docs/guides/structured-outputs
    client = OpenAI()
    response = client.responses.parse(
        model="gpt-5.6",
        input=[
            {
                "role": "system",
                "content": (
                    "Preserve the job posting's factual information. Extract its key job "
                    "qualifications, using 1-5 words per qualification, and save them in "
                    "the qualifications field."
                ),
            },
            {
                "role": "user",
                "content": JobPostingRead.model_validate(job_posting).model_dump_json(),
            },
        ],
        text_format=JobPostingEnrichment,
    )

    if response.output_parsed is None:
        raise ValueError("OpenAI returned no parsed job posting")

    enriched = JobPosting.model_validate(job_posting.model_dump())
    enriched.qualifications = response.output_parsed.qualifications
    return enriched
