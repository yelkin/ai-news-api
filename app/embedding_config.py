"""Changing these constants requires a migration and re-embedding stored jobs."""

EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMENSIONS = 1536
EMBEDDING_VERSION = f"{EMBEDDING_MODEL}:{EMBEDDING_DIMENSIONS}:title-description-v1"
