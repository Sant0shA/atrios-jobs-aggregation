from dateutil.parser import parse
import feedparser

from app.fetchers.base import BaseFetcher


class WeWorkRemotelyFetcher(BaseFetcher):
    source_name = "weworkremotely"
    url = "https://weworkremotely.com/remote-jobs.rss"

    async def fetch(self) -> list[dict]:
        feed = feedparser.parse(self.url)
        normalized = []
        for entry in feed.entries:
            normalized.append(
                {
                    "external_job_id": entry.get("id") or entry.get("guid"),
                    "title": entry.get("title"),
                    "company": entry.get("author"),
                    "location": None,
                    "description": entry.get("summary"),
                    "url": entry.get("link"),
                    "posted_at": parse(entry["published"]) if entry.get("published") else None,
                    "job_type": "remote",
                    "raw": dict(entry),
                }
            )
        return normalized
