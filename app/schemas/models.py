from pydantic import BaseModel, Field


class JobPosting(BaseModel):
    platform: str
    company: str
    title: str
    description: str
    tags: list[str]
    qualifications: list[str] = Field(default_factory=list)
