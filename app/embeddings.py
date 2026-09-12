"""Bulk embedding of job titles and descriptions, with resumable database writes."""

import logging
import math
from collections.abc import Callable, Sequence
from functools import lru_cache
from html.parser import HTMLParser

import tiktoken
from openai import OpenAI
from sqlalchemy import func, or_, update
from sqlmodel import Session, select

from app.embedding_config import (
    EMBEDDING_DIMENSIONS,
    EMBEDDING_MODEL,
    EMBEDDING_VERSION,
)
from app.schemas.models import EmbeddingSummary, JobPosting

logger = logging.getLogger(__name__)
MAX_INPUT_TOKENS = 8000
MAX_BATCH_TOKENS = 16000
MAX_BATCH_JOBS = 64
EmbeddingProvider = Callable[[list[str]], list[list[float]]]


class PlainText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style"}:
            self.hidden += 1
        self.parts.append(" ")

    def handle_endtag(self, tag):
        if tag in {"script", "style"}:
            self.hidden = max(0, self.hidden - 1)
        self.parts.append(" ")

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


def plain_text(value: str) -> str:
    parser = PlainText()
    parser.feed(value)
    parser.close()
    return " ".join("".join(parser.parts).split())


@lru_cache(maxsize=1)
def encoding():
    return tiktoken.get_encoding("cl100k_base")


def tokenize(value: str) -> list[int]:
    return encoding().encode(value, disallowed_special=())


def truncate(value: str, max_tokens: int) -> str:
    tokens = tokenize(value)
    return encoding().decode(tokens[:max_tokens], errors="ignore")


def posting_text(title: str, description: str) -> str:
    """As a user, I can search jobs by the meaning of their title and description."""
    title = truncate(plain_text(title), 512)
    return truncate(
        f"Title: {title}\nDescription: {plain_text(description)}", MAX_INPUT_TOKENS
    )


def token_batches(texts: Sequence[str]) -> list[list[int]]:
    """Partition an already bounded page without exceeding provider request limits."""
    batches, batch, total = [], [], 0
    for index, value in enumerate(texts):
        size = len(tokenize(value))
        if not 0 < size <= MAX_INPUT_TOKENS:
            raise ValueError("Embedding input exceeds the token limit or is empty")
        if batch and (total + size > MAX_BATCH_TOKENS or len(batch) >= MAX_BATCH_JOBS):
            batches.append(batch)
            batch, total = [], 0
        batch.append(index)
        total += size
    if batch:
        batches.append(batch)
    return batches


def validate_vectors(vectors: Sequence[Sequence[float]], count: int) -> None:
    if len(vectors) != count:
        raise ValueError("Embedding count does not match input count")
    for vector in vectors:
        if len(vector) != EMBEDDING_DIMENSIONS:
            raise ValueError("Embedding dimensions do not match the database")
        if not all(math.isfinite(v) and abs(v) <= 3.4e38 for v in vector) or not any(
            vector
        ):
            raise ValueError("Embedding must be a finite nonzero vector")


def normalize_vectors(vectors):
    validate_vectors(vectors, len(vectors))
    result = []
    for row in vectors:
        norm = math.sqrt(sum(float(x) ** 2 for x in row))
        result.append([float(v) / norm for v in row])
    return result


def ordered_vectors(data, count: int) -> list[list[float]]:
    """Associate provider output with input positions, independent of result order."""
    if sorted(item.index for item in data) != list(range(count)):
        raise ValueError("Embedding response indexes do not match inputs")
    vectors = [item.embedding for item in sorted(data, key=lambda item: item.index)]
    validate_vectors(vectors, count)
    return vectors


def embed_texts(texts: list[str]) -> list[list[float]]:
    # https://developers.openai.com/api/docs/guides/embeddings
    with OpenAI(timeout=60.0, max_retries=2) as client:
        response = client.embeddings.create(
            model=EMBEDDING_MODEL,
            dimensions=EMBEDDING_DIMENSIONS,
            input=texts,
            encoding_format="float",
        )
    return ordered_vectors(response.data, len(texts))


def get_embedding_provider() -> EmbeddingProvider:
    return embed_texts


def missing_embedding():
    return or_(
        JobPosting.embedding.is_(None),
        JobPosting.embedding_version.is_(None),
        JobPosting.embedding_version != EMBEDDING_VERSION,
    )


def embed_missing_jobs(
    session: Session, provider: EmbeddingProvider, max_jobs: int | None = None
) -> EmbeddingSummary:
    """As a user, I can embed all missing jobs in batches and retry unfinished work."""
    summary = EmbeddingSummary()
    upper_id = session.exec(select(func.max(JobPosting.id))).one() or 0
    session.rollback()  # Release the read transaction before calling the provider.
    last_id = 0
    while max_jobs is None or summary.selected < max_jobs:
        page_size = (
            MAX_BATCH_JOBS
            if max_jobs is None
            else min(MAX_BATCH_JOBS, max_jobs - summary.selected)
        )
        rows = session.exec(
            select(JobPosting.id, JobPosting.title, JobPosting.description)
            .where(
                JobPosting.id > last_id, JobPosting.id <= upper_id, missing_embedding()
            )
            .order_by(JobPosting.id)
            .limit(page_size)
        ).all()
        session.rollback()
        if not rows:
            break
        last_id = rows[-1].id
        texts = [posting_text(row.title, row.description) for row in rows]
        for indexes in token_batches(texts):
            batch = [rows[i] for i in indexes]
            summary.selected += len(batch)
            try:
                vectors = normalize_vectors(provider([texts[i] for i in indexes]))
                validate_vectors(vectors, len(batch))
                written = 0
                for row, vector in zip(batch, vectors, strict=True):
                    # Compare source fields atomically to reject concurrent scrape changes.
                    result = session.execute(
                        update(JobPosting)
                        .where(
                            JobPosting.id == row.id,
                            JobPosting.title == row.title,
                            JobPosting.description == row.description,
                            missing_embedding(),
                        )
                        .values(embedding=vector, embedding_version=EMBEDDING_VERSION)
                        .execution_options(synchronize_session=False)
                    )
                    written += result.rowcount
                session.commit()
                summary.embedded += written
                summary.skipped += len(batch) - written
            except Exception:
                session.rollback()
                logger.exception(
                    "Embedding batch failed for job IDs %s", [row.id for row in batch]
                )
                summary.failed += len(batch)
                if len(summary.errors) < 100:
                    summary.errors.append(
                        f"Embedding failed for job IDs {[row.id for row in batch]}; retry the request."
                    )
    return summary
