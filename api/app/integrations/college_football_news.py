from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html import unescape
from urllib.parse import urljoin, urlparse
import xml.etree.ElementTree as ET

import httpx
from bs4 import BeautifulSoup


CFN_SOURCE_NAME = "College Football News"
CFN_HOME_URL = "https://collegefootballnews.com/"
CFN_FEED_URLS = (
    "https://collegefootballnews.com/feed",
    "https://collegefootballnews.com/rss",
    "https://collegefootballnews.com/college-football/feed",
    "https://collegefootballnews.com/news/feed",
)
USER_AGENT = "CollegeFootballFantasyApp/1.0 (+https://collegefootballfantasy.app; metadata-only news fetch)"


@dataclass
class CollegeFootballNewsEntry:
    title: str
    link: str
    summary: str | None = None
    published_at: datetime | None = None
    external_id: str | None = None
    raw_payload: dict | None = None


def _clean_text(value: str | None) -> str:
    if not value:
        return ""
    if "<" not in value and ">" not in value:
        return " ".join(unescape(value).split())
    return " ".join(unescape(BeautifulSoup(value, "html.parser").get_text(" ")).split())


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = parsedate_to_datetime(value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except (TypeError, ValueError):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)
        except ValueError:
            return None


def parse_feed_entries(xml_text: str, *, base_url: str = CFN_HOME_URL) -> list[CollegeFootballNewsEntry]:
    root = ET.fromstring(xml_text.strip())
    entries: list[CollegeFootballNewsEntry] = []
    namespaces = {
        "atom": "http://www.w3.org/2005/Atom",
        "content": "http://purl.org/rss/1.0/modules/content/",
        "dc": "http://purl.org/dc/elements/1.1/",
    }
    rss_items = root.findall(".//item")
    atom_items = root.findall(".//atom:entry", namespaces)
    for item in rss_items:
        title = _clean_text(item.findtext("title"))
        link = _clean_text(item.findtext("link"))
        summary = _clean_text(item.findtext("description")) or None
        published_at = _parse_datetime(item.findtext("pubDate") or item.findtext("dc:date", namespaces))
        external_id = _clean_text(item.findtext("guid")) or link
        if title and link:
            entries.append(
                CollegeFootballNewsEntry(
                    title=title,
                    link=urljoin(base_url, link),
                    summary=summary,
                    published_at=published_at,
                    external_id=external_id,
                    raw_payload={"source": "rss", "guid": external_id},
                )
            )
    for item in atom_items:
        title = _clean_text(item.findtext("atom:title", namespaces))
        link_node = item.find("atom:link", namespaces)
        href = link_node.attrib.get("href") if link_node is not None else ""
        summary = _clean_text(item.findtext("atom:summary", namespaces) or item.findtext("atom:content", namespaces)) or None
        published_at = _parse_datetime(item.findtext("atom:published", namespaces) or item.findtext("atom:updated", namespaces))
        external_id = _clean_text(item.findtext("atom:id", namespaces)) or href
        if title and href:
            entries.append(
                CollegeFootballNewsEntry(
                    title=title,
                    link=urljoin(base_url, href),
                    summary=summary,
                    published_at=published_at,
                    external_id=external_id,
                    raw_payload={"source": "atom", "id": external_id},
                )
            )
    return entries


def parse_index_entries(html_text: str, *, base_url: str = CFN_HOME_URL, limit: int = 50) -> list[CollegeFootballNewsEntry]:
    soup = BeautifulSoup(html_text, "html.parser")
    entries: list[CollegeFootballNewsEntry] = []
    seen: set[str] = set()
    base_host = urlparse(base_url).netloc
    blocked_text = {
        "about us",
        "news",
        "college football",
        "predictions",
        "rankings",
        "schedules",
        "bowl projections",
        "betting",
        "nfl draft",
        "site map",
        "privacy policy",
        "terms of use",
        "see more",
    }
    for anchor in soup.find_all("a", href=True):
        title = _clean_text(anchor.get_text(" "))
        if len(title) < 18 or title.lower() in blocked_text:
            continue
        link = urljoin(base_url, anchor["href"])
        parsed = urlparse(link)
        if parsed.netloc and parsed.netloc != base_host:
            continue
        if link in seen:
            continue
        seen.add(link)
        parent_text = _clean_text(anchor.parent.get_text(" ") if anchor.parent else "")
        summary = parent_text.replace(title, "").strip(" -–—")[:280] or None
        entries.append(
            CollegeFootballNewsEntry(
                title=title,
                link=link,
                summary=summary,
                external_id=link,
                raw_payload={"source": "html_index"},
            )
        )
        if len(entries) >= limit:
            break
    return entries


class CollegeFootballNewsProvider:
    def __init__(self, timeout_seconds: float = 10.0) -> None:
        self.timeout_seconds = timeout_seconds

    def fetch_entries(self, *, limit: int = 50) -> list[CollegeFootballNewsEntry]:
        headers = {"User-Agent": USER_AGENT, "Accept": "application/rss+xml, application/atom+xml, text/xml, text/html"}
        with httpx.Client(timeout=self.timeout_seconds, follow_redirects=True, headers=headers) as client:
            for feed_url in CFN_FEED_URLS:
                try:
                    response = client.get(feed_url)
                    if response.status_code >= 400:
                        continue
                    entries = parse_feed_entries(response.text, base_url=CFN_HOME_URL)
                    if entries:
                        return entries[:limit]
                except (httpx.HTTPError, ET.ParseError):
                    continue
            response = client.get(CFN_HOME_URL)
            response.raise_for_status()
            return parse_index_entries(response.text, base_url=CFN_HOME_URL, limit=limit)
