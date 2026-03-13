from datetime import datetime, timedelta, timezone

from fastapi import Depends, FastAPI, HTTPException, Query
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.database import Base, engine, get_db
from app.fetcher import run_all_sources, run_source, seed_default_sources
from app.models import FetchRun, Job, JobSource
from app.schemas import FetchTriggerResponse, JobSearchResponse, SourceCreate, SourceRead
from app.scheduler import start_scheduler, stop_scheduler

app = FastAPI(title="Jobs Ingestion Platform", version="1.0.0")


@app.on_event("startup")
def on_startup() -> None:
    Base.metadata.create_all(bind=engine)
    db = next(get_db())
    try:
        seed_default_sources(db)
    finally:
        db.close()
    start_scheduler()


@app.on_event("shutdown")
def on_shutdown() -> None:
    stop_scheduler()


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/build-check")
def build_check() -> dict:
    return {"service": "jobs-ingestion-platform", "build": "phase-1"}


@app.post("/api/sources", response_model=SourceRead)
def create_source(payload: SourceCreate, db: Session = Depends(get_db)):
    existing = db.scalar(select(JobSource).where(JobSource.source_name == payload.source_name))
    if existing:
        raise HTTPException(status_code=400, detail="Source with this name already exists")
    source = JobSource(**payload.model_dump())
    db.add(source)
    db.commit()
    db.refresh(source)
    return source


@app.get("/api/sources", response_model=list[SourceRead])
def list_sources(db: Session = Depends(get_db)):
    return db.scalars(select(JobSource).order_by(JobSource.id.asc())).all()


@app.post("/api/sources/{source_id}/fetch", response_model=FetchTriggerResponse)
async def fetch_source(source_id: int, db: Session = Depends(get_db)):
    source = db.get(JobSource, source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    run = await run_source(db, source)
    return FetchTriggerResponse(message="Fetch completed", source_id=source.id, run_ids=[run.id])


@app.get("/api/jobs/search", response_model=list[JobSearchResponse])
def search_jobs(
    q: str | None = Query(None),
    company: str | None = Query(None),
    status: str = Query("active"),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    stmt = select(Job).where(Job.status == status)
    if q:
        like = f"%{q.lower()}%"
        stmt = stmt.where(Job.normalized_title.like(like))
    if company:
        like_company = f"%{company.lower()}%"
        stmt = stmt.where(Job.normalized_company.like(like_company))
    stmt = stmt.order_by(desc(Job.last_seen_at)).limit(limit)
    return db.scalars(stmt).all()


@app.get("/api/jobs/new-this-week", response_model=list[JobSearchResponse])
def new_this_week(db: Session = Depends(get_db)):
    cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    stmt = select(Job).where(Job.first_seen_at >= cutoff).order_by(desc(Job.first_seen_at)).limit(100)
    return db.scalars(stmt).all()


@app.get("/api/fetch-runs/recent")
def recent_fetch_runs(limit: int = Query(20, ge=1, le=100), db: Session = Depends(get_db)):
    stmt = select(FetchRun).order_by(desc(FetchRun.started_at)).limit(limit)
    runs = db.scalars(stmt).all()
    return [
        {
            "id": run.id,
            "source_id": run.source_id,
            "started_at": run.started_at,
            "completed_at": run.completed_at,
            "status": run.status,
            "jobs_found": run.jobs_found,
            "jobs_inserted": run.jobs_inserted,
            "jobs_updated": run.jobs_updated,
            "jobs_skipped_duplicate": run.jobs_skipped_duplicate,
            "error_message": run.error_message,
        }
        for run in runs
    ]


@app.post("/api/fetch-runs/trigger-all", response_model=FetchTriggerResponse)
async def trigger_all_fetches(db: Session = Depends(get_db)):
    runs = await run_all_sources(db)
    return FetchTriggerResponse(message="All active sources processed", run_ids=[run.id for run in runs])
