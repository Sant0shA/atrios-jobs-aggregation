from dateutil.parser import parse
import httpx

from app.fetchers.base import BaseFetcher


class RemoteOkFetcher(BaseFetcher):
    source_name = "remoteok"
    url = "https://remoteok.com/api"

    async def fetch(self) -> list[dict]:
        headers = {"User-Agent": "atrios-jobs-ingestion/1.0"}
        async with httpx.AsyncClient(timeout=30, headers=headers) as client:
            response = await client.get(self.url)
            response.raise_for_status()
        payload = response.json()
        jobs = payload[1:] if isinstance(payload, list) and payload else []
        normalized = []
        for item in jobs:
            normalized.append(
                {
                    "external_job_id": str(item.get("id")) if item.get("id") else None,
                    "title": item.get("position") or item.get("title"),
                    "company": item.get("company"),
                    "location": item.get("location"),
                    "description": item.get("description"),
                    "url": item.get("url"),
                    "posted_at": parse(item["date"]) if item.get("date") else None,
                    "job_type": "remote",
                    "raw": item,
                }
            )
        return normalized
