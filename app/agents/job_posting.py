from openai import OpenAI

from app.schemas.models import JobPosting


def enrich_job_posting(job_posting: JobPosting) -> JobPosting:
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
            {"role": "user", "content": job_posting.model_dump_json()},
        ],
        text_format=JobPosting,
    )

    if response.output_parsed is None:
        raise ValueError("OpenAI returned no parsed job posting")

    return response.output_parsed
