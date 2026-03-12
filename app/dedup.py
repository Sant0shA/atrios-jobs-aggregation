import hashlib
import re


def normalize_text(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"\s+", " ", value.strip().lower())


def normalize_url(value: str | None) -> str | None:
    if not value:
        return None
    cleaned = value.strip()
    return cleaned.rstrip("/")


def build_content_hash(title: str | None, company: str | None, location: str | None) -> str:
    payload = "|".join([normalize_text(title), normalize_text(company), normalize_text(location)])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def build_cluster_id(title: str | None, company: str | None) -> str:
    payload = "|".join([normalize_text(title), normalize_text(company)])
    return hashlib.md5(payload.encode("utf-8")).hexdigest()
