"""Best-effort RSS news feed. Headlines stay attributed to their publisher."""
from __future__ import annotations
import asyncio, time, xml.etree.ElementTree as ET, re, html
import httpx

DEFAULT_FEEDS = [
    ("Cointelegraph", "https://cointelegraph.com/rss"),
    ("Bitcoin Magazine", "https://bitcoinmagazine.com/.rss/full/"),
]

class NewsService:
    def __init__(self, feeds=None):
        self.feeds = feeds or DEFAULT_FEEDS
        self.cache = {"items": [], "updated_at": 0, "status": "Not fetched"}
        self.client = httpx.AsyncClient(timeout=8, headers={"User-Agent":"MIRAGE-News/1.0"})

    async def close(self): await self.client.aclose()

    async def refresh(self):
        async def load(name, url):
            try:
                r = await self.client.get(url)
                r.raise_for_status()
                root = ET.fromstring(r.text)
                out = []
                for item in root.findall(".//item")[:15]:
                    title = (item.findtext("title") or "").strip()
                    link = (item.findtext("link") or "").strip()
                    pub = (item.findtext("pubDate") or "").strip()
                    desc = (item.findtext("description") or "").strip()
                    if title and link.startswith("http"):
                        out.append({"source":name,"title":title,"url":link,"published":pub,
                                    "summary":re.sub(r"<[^>]+>", " ", html.unescape(desc))[:400]})
                return out
            except Exception:
                return []
        groups = await asyncio.gather(*(load(n,u) for n,u in self.feeds))
        items = [x for group in groups for x in group]
        self.cache = {"items":items[:30], "updated_at":int(time.time()),
                      "status":"Live RSS" if items else "Sources temporarily unavailable"}
        return self.cache

    async def get(self):
        if time.time() - self.cache["updated_at"] > 600:
            return await self.refresh()
        return self.cache
