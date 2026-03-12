from datetime import datetime

from pydantic import BaseModel, Field


class SourceCreate(BaseModel):
    source_name: str
    source_label: str
    url: str
    source_category: str | None = None
    is_active: bool = True
    fetch_mode: str = "scheduled"


class SourceRead(SourceCreate):
    id: int
    last_checked_at: datetime | None = None
    last_successful_run_at: datetime | None = None
    last_failure_log: str | None = None
    consecutive_failures: int

    class Config:
        from_attributes = True


class JobSearchResponse(BaseModel):
    id: int
    title: str
    company: str
    location: str | None
    job_url: str | None
    status: str
    posted_at: datetime | None
    last_seen_at: datetime

    class Config:
        from_attributes = True


class FetchTriggerResponse(BaseModel):
    message: str
    source_id: int | None = None
    run_ids: list[int] = Field(default_factory=list)
