from datetime import datetime, timedelta, timezone

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.dedup import build_cluster_id, build_content_hash, normalize_text, normalize_url
from app.fetchers.ncs import NcsFetcher
from app.fetchers.remotive import RemotiveFetcher
from app.fetchers.remoteok import RemoteOkFetcher
from app.fetchers.weworkremotely import WeWorkRemotelyFetcher
from app.models import FetchRun, Job, JobSource, JobSourceLink, RawJob

FETCHERS = {
    "remotive": RemotiveFetcher,
    "remoteok": RemoteOkFetcher,
    "weworkremotely": WeWorkRemotelyFetcher,
    "ncs": NcsFetcher,
}


async def run_source(db: Session, source: JobSource) -> FetchRun:
    run = FetchRun(source_id=source.id, status="running")
    db.add(run)
    db.commit()
    db.refresh(run)

    now = datetime.now(timezone.utc)
    source.last_checked_at = now

    fetcher_cls = FETCHERS.get(source.source_name)
    if not fetcher_cls:
        run.status = "failed"
        run.error_message = f"No fetcher configured for {source.source_name}"
        run.completed_at = datetime.now(timezone.utc)
        source.consecutive_failures += 1
        source.last_failure_log = run.error_message
        db.commit()
        return run

    try:
        jobs = await fetcher_cls().fetch()
        run.jobs_found = len(jobs)

        seen_job_ids = set()
        for item in jobs:
            raw = RawJob(
                source_id=source.id,
                fetch_run_id=run.id,
                external_job_id=item.get("external_job_id"),
                raw_payload_json=item.get("raw", {}),
                raw_title=item.get("title"),
                raw_company=item.get("company"),
                raw_location=item.get("location"),
                raw_description=item.get("description"),
                raw_posted_at=item.get("posted_at"),
                raw_url=item.get("url"),
            )
            db.add(raw)

            normalized_url = normalize_url(item.get("url"))
            content_hash = build_content_hash(item.get("title"), item.get("company"), item.get("location"))
            cluster_id = build_cluster_id(item.get("title"), item.get("company"))

            query = select(Job)
            if normalized_url:
                query = query.where(Job.job_url == normalized_url)
                existing = db.scalar(query)
            else:
                existing = None

            if not existing:
                existing = db.scalar(select(Job).where(Job.content_hash == content_hash))

            if not existing:
                existing = db.scalar(
                    select(Job).where(
                        Job.normalized_title == normalize_text(item.get("title")),
                        Job.normalized_company == normalize_text(item.get("company")),
                    )
                )

            if existing:
                existing.last_seen_at = now
                existing.consecutive_misses = 0
                existing.status = "active"
                if not existing.job_url and normalized_url:
                    existing.job_url = normalized_url
                run.jobs_updated += 1
                run.jobs_skipped_duplicate += 1
                seen_job_ids.add(existing.id)
                job = existing
            else:
                job = Job(
                    primary_source_id=source.id,
                    title=item.get("title") or "Untitled role",
                    normalized_title=normalize_text(item.get("title")),
                    company=item.get("company") or "Unknown company",
                    normalized_company=normalize_text(item.get("company")),
                    location=item.get("location"),
                    location_type="remote" if "remote" in normalize_text(item.get("location")) else None,
                    city=None,
                    country="India" if source.source_name == "ncs" else None,
                    description=item.get("description"),
                    job_url=normalized_url,
                    job_type=item.get("job_type"),
                    posted_at=item.get("posted_at"),
                    first_seen_at=now,
                    last_seen_at=now,
                    status="active",
                    consecutive_misses=0,
                    content_hash=content_hash,
                    dedupe_cluster_id=cluster_id,
                    skills_json={},
                )
                db.add(job)
                db.flush()
                run.jobs_inserted += 1
                seen_job_ids.add(job.id)

            link = db.scalar(
                select(JobSourceLink).where(JobSourceLink.job_id == job.id, JobSourceLink.source_id == source.id)
            )
            if link:
                link.last_seen_at = now
                if normalized_url:
                    link.source_job_url = normalized_url
            else:
                db.add(
                    JobSourceLink(
                        job_id=job.id,
                        source_id=source.id,
                        source_job_url=normalized_url,
                        first_seen_at=now,
                        last_seen_at=now,
                    )
                )

        source_jobs = db.scalars(
            select(Job)
            .where(
                or_(
                    Job.primary_source_id == source.id,
                    Job.id.in_(
                        select(JobSourceLink.job_id).where(JobSourceLink.source_id == source.id)
                    ),
                )
            )
        ).all()

        for job in source_jobs:
            if job.id in seen_job_ids:
                continue
            job.consecutive_misses += 1
            if job.consecutive_misses >= 3:
                job.status = "suspected_closed"
            if job.last_seen_at and job.last_seen_at < now - timedelta(days=30):
                job.status = "archived"

        run.status = "success"
        source.last_successful_run_at = datetime.now(timezone.utc)
        source.consecutive_failures = 0
        source.last_failure_log = None
    except Exception as exc:
        run.status = "failed"
        run.error_message = str(exc)
        source.consecutive_failures += 1
        source.last_failure_log = str(exc)

    run.completed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(run)
    return run


async def run_all_sources(db: Session) -> list[FetchRun]:
    runs = []
    sources = db.scalars(select(JobSource).where(JobSource.is_active.is_(True))).all()
    for source in sources:
        run = await run_source(db, source)
        runs.append(run)
    return runs


def seed_default_sources(db: Session) -> None:
    defaults = [
        ("remotive", "Remotive API", "https://remotive.com/api/remote-jobs", "api"),
        ("remoteok", "Remote OK API", "https://remoteok.com/api", "api"),
        ("weworkremotely", "We Work Remotely RSS", "https://weworkremotely.com/remote-jobs.rss", "rss"),
        ("ncs", "NCS India API", "https://www.ncs.gov.in", "api"),
    ]
    for name, label, url, category in defaults:
        existing = db.scalar(select(JobSource).where(JobSource.source_name == name))
        if not existing:
            db.add(
                JobSource(
                    source_name=name,
                    source_label=label,
                    url=url,
                    source_category=category,
                    is_active=True,
                    fetch_mode="scheduled",
                )
            )
    db.commit()
