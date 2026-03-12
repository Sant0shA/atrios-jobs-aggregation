from dateutil.parser import parse
import httpx

from app.fetchers.base import BaseFetcher


class RemotiveFetcher(BaseFetcher):
    source_name = "remotive"
    url = "https://remotive.com/api/remote-jobs"

    async def fetch(self) -> list[dict]:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(self.url)
            response.raise_for_status()
        jobs = response.json().get("jobs", [])
        normalized = []
        for item in jobs:
            normalized.append(
                {
                    "external_job_id": str(item.get("id")),
                    "title": item.get("title"),
                    "company": item.get("company_name"),
                    "location": item.get("candidate_required_location"),
                    "description": item.get("description"),
                    "url": item.get("url"),
                    "posted_at": parse(item["publication_date"]) if item.get("publication_date") else None,
                    "job_type": item.get("job_type"),
                    "raw": item,
                }
            )
        return normalized
