import httpx

from app.fetchers.base import BaseFetcher


class NcsFetcher(BaseFetcher):
    source_name = "ncs"
    url = "https://www.ncs.gov.in/_vti_bin/NCSServices/JobsAPI.svc/get"

    async def fetch(self) -> list[dict]:
        # Public NCS endpoint formats can vary; this parser is intentionally defensive.
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(self.url)
            response.raise_for_status()
        payload = response.json()
        rows = payload.get("d") if isinstance(payload, dict) else []
        if not isinstance(rows, list):
            rows = []
        normalized = []
        for item in rows:
            normalized.append(
                {
                    "external_job_id": str(item.get("JobId")) if item.get("JobId") else None,
                    "title": item.get("JobTitle"),
                    "company": item.get("CompanyName"),
                    "location": item.get("JobLocation"),
                    "description": item.get("JobDescription"),
                    "url": item.get("JobDetailUrl") or item.get("ApplyUrl"),
                    "posted_at": None,
                    "job_type": item.get("JobType"),
                    "raw": item,
                }
            )
        return normalized
