"""Best-effort RSS news feed with attributed titles and publisher images."""
from __future__ import annotations

import asyncio
import html
import re
import time
import xml.etree.ElementTree as ET
from urllib.parse import urljoin, urlparse

import httpx

DEFAULT_FEEDS = [
    ("Cointelegraph", "https://cointelegraph.com/rss"),
    ("Bitcoin Magazine", "https://bitcoinmagazine.com/.rss/full/"),
]


def _safe_http_url(value: str, base: str = "") -> str | None:
    candidate = urljoin(base, html.unescape((value or "").strip())) if base else html.unescape((value or "").strip())
    parsed = urlparse(candidate)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    return candidate


def _extract_image(item: ET.Element, description: str, article_url: str) -> str | None:
    # RSS media:content / media:thumbnail, Atom links, and image enclosures.
    for node in item.iter():
        tag = node.tag.rsplit("}", 1)[-1].lower()
        attrs = {str(k).rsplit("}", 1)[-1].lower(): str(v) for k, v in node.attrib.items()}
        candidate = None
        if tag in {"content", "thumbnail", "enclosure", "image"}:
            candidate = attrs.get("url") or attrs.get("href") or attrs.get("src")
            mime = attrs.get("type", "").lower()
            if tag == "enclosure" and mime and not mime.startswith("image/"):
                candidate = None
        if candidate:
            safe = _safe_http_url(candidate, article_url)
            if safe:
                return safe

    # Some feeds put a lead image only in the HTML description.
    match = re.search(r"(?:src|data-src)\s*=\s*['\"]([^'\"]+)['\"]", html.unescape(description or ""), re.I)
    if match:
        return _safe_http_url(match.group(1), article_url)
    return None


def _plain_summary(raw: str) -> str:
    text = re.sub(r"<\s*(script|style)[^>]*>.*?<\s*/\s*\1\s*>", " ", raw or "", flags=re.I | re.S)
    text = re.sub(r"<[^>]+>", " ", html.unescape(text))
    return re.sub(r"\s+", " ", text).strip()[:400]


class NewsService:
    def __init__(self, feeds=None):
        self.feeds = feeds or DEFAULT_FEEDS
        self.cache = {"items": [], "updated_at": 0, "status": "Not fetched"}
        self.client = httpx.AsyncClient(timeout=8, headers={"User-Agent": "MIRAGE-News/1.4"})

    async def close(self):
        await self.client.aclose()

    async def refresh(self):
        async def load(name, url):
            try:
                response = await self.client.get(url)
                response.raise_for_status()
                root = ET.fromstring(response.text)
                out = []
                entries = root.findall(".//item") or root.findall(".//{http://www.w3.org/2005/Atom}entry")
                for item in entries[:15]:
                    title = (item.findtext("title") or item.findtext("{http://www.w3.org/2005/Atom}title") or "").strip()
                    link = (item.findtext("link") or "").strip()
                    if not link:
                        for link_node in item.findall("{http://www.w3.org/2005/Atom}link"):
                            if link_node.attrib.get("rel", "alternate") == "alternate":
                                link = link_node.attrib.get("href", "")
                                break
                    link = _safe_http_url(link, url)
                    pub = (item.findtext("pubDate") or item.findtext("{http://www.w3.org/2005/Atom}updated") or "").strip()
                    description = (item.findtext("description") or item.findtext("{http://www.w3.org/2005/Atom}summary") or "").strip()
                    if title and link:
                        out.append({
                            "source": name,
                            "title": _plain_summary(title)[:220],
                            "url": link,
                            "published": pub[:80],
                            "summary": _plain_summary(description),
                            "image": _extract_image(item, description, link),
                        })
                return out
            except Exception:
                return []

        groups = await asyncio.gather(*(load(name, url) for name, url in self.feeds))
        items = [item for group in groups for item in group]
        self.cache = {
            "items": items[:30],
            "updated_at": int(time.time()),
            "status": "Live RSS" if items else "Sources temporarily unavailable",
        }
        return self.cache

    async def get(self):
        if time.time() - self.cache["updated_at"] > 600:
            return await self.refresh()
        return self.cache
