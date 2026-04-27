"""Website source CRUD and ingestion service."""

import re
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse, urldefrag

import httpx
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import WebsiteSourceCreate, WebsiteSourceUpdate
from app.core.logging import logger
from app.models.website_source import WebsiteContentChunk, WebsiteSource


class WebsiteSourceService:
    """Manage website sources and persist extracted content chunks."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_sources(self) -> list[WebsiteSource]:
        result = await self.db.execute(
            select(WebsiteSource).order_by(WebsiteSource.priority.asc(), WebsiteSource.created_at.asc())
        )
        return list(result.scalars().all())

    async def list_enabled_sources(self) -> list[WebsiteSource]:
        result = await self.db.execute(
            select(WebsiteSource)
            .where(WebsiteSource.is_enabled.is_(True))
            .order_by(WebsiteSource.priority.asc(), WebsiteSource.created_at.asc())
        )
        return list(result.scalars().all())

    async def get_source(self, source_id: int) -> WebsiteSource | None:
        return await self.db.get(WebsiteSource, source_id)

    async def create_source(self, data: WebsiteSourceCreate) -> WebsiteSource:
        source = WebsiteSource(
            name=data.name.strip(),
            base_url=self._normalize_url(data.base_url),
            is_enabled=data.is_enabled,
            priority=data.priority,
            notes=data.notes,
            max_pages=data.max_pages,
        )
        self.db.add(source)
        await self.db.flush()
        await self.db.refresh(source)
        return source

    async def update_source(self, source: WebsiteSource, data: WebsiteSourceUpdate) -> WebsiteSource:
        if data.name is not None:
            source.name = data.name.strip()
        if data.base_url is not None:
            source.base_url = self._normalize_url(data.base_url)
        if data.is_enabled is not None:
            source.is_enabled = data.is_enabled
        if data.priority is not None:
            source.priority = data.priority
        if data.notes is not None:
            source.notes = data.notes
        if data.max_pages is not None:
            source.max_pages = data.max_pages
        await self.db.flush()
        await self.db.refresh(source)
        return source

    async def delete_source(self, source: WebsiteSource) -> None:
        await self.db.delete(source)

    async def refresh_all_sources(self) -> dict:
        sources = [s for s in await self.list_sources() if s.is_enabled]
        refreshed = 0
        failed = 0
        for source in sources:
            result = await self.refresh_source(source)
            if result["status"] == "success":
                refreshed += 1
            else:
                failed += 1
        return {"status": "success", "refreshed": refreshed, "failed": failed}

    async def refresh_source(self, source: WebsiteSource) -> dict:
        """Fetch website pages and replace stored chunks for a source."""
        try:
            pages = await self._crawl_source(source)
            await self.db.execute(
                delete(WebsiteContentChunk).where(WebsiteContentChunk.source_id == source.id)
            )

            saved = 0
            for page in pages:
                if not page["content"]:
                    continue
                self.db.add(
                    WebsiteContentChunk(
                        source_id=source.id,
                        page_url=page["page_url"],
                        title=page["title"],
                        content=page["content"],
                    )
                )
                saved += 1

            source.last_crawled_at = datetime.now(timezone.utc)
            source.last_status = f"success:{saved}"
            await self.db.flush()
            logger.info(f"Refreshed website source {source.id} with {saved} chunks")
            return {"status": "success", "source_id": source.id, "chunks": saved}
        except Exception as e:
            source.last_crawled_at = datetime.now(timezone.utc)
            source.last_status = f"failed:{type(e).__name__}"
            await self.db.flush()
            logger.error(f"Website source refresh failed for {source.base_url}: {e!r}")
            return {"status": "failed", "source_id": source.id, "detail": str(e)}

    async def build_context_from_source_ids(self, source_ids: list[int], limit: int = 6) -> str:
        if not source_ids:
            return ""
        result = await self.db.execute(
            select(WebsiteContentChunk, WebsiteSource)
            .join(WebsiteSource, WebsiteSource.id == WebsiteContentChunk.source_id)
            .where(WebsiteContentChunk.source_id.in_(source_ids))
            .order_by(WebsiteSource.priority.asc(), WebsiteContentChunk.created_at.desc())
        )
        rows = result.all()
        snippets: list[str] = []
        for chunk, source in rows[:limit]:
            snippets.append(
                f"Source {source.name} ({chunk.page_url}) | {chunk.content[:700]}"
            )
        return "\n".join(snippets)

    async def build_context_for_source(self, source_id: int, limit: int = 4) -> str:
        return await self.build_context_from_source_ids([source_id], limit=limit)

    async def build_context_from_enabled_sources(self, limit: int = 8) -> str:
        result = await self.db.execute(
            select(WebsiteContentChunk, WebsiteSource)
            .join(WebsiteSource, WebsiteSource.id == WebsiteContentChunk.source_id)
            .where(WebsiteSource.is_enabled.is_(True))
            .order_by(WebsiteSource.priority.asc(), WebsiteContentChunk.created_at.desc())
        )
        rows = result.all()
        snippets: list[str] = []
        for chunk, source in rows[:limit]:
            snippets.append(
                f"Source {source.name} ({chunk.page_url}) | {chunk.content[:700]}"
            )
        return "\n".join(snippets)

    async def _crawl_source(self, source: WebsiteSource) -> list[dict]:
        base_url = self._normalize_url(source.base_url)
        origin = urlparse(base_url).netloc
        to_visit = [base_url]
        seen: set[str] = set()
        pages: list[dict] = []

        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
            while to_visit and len(seen) < max(source.max_pages, 1):
                current = to_visit.pop(0)
                if current in seen:
                    continue
                seen.add(current)
                try:
                    response = await client.get(current)
                    response.raise_for_status()
                except Exception as e:
                    logger.warning(f"Skipping page {current}: {e}")
                    continue

                html = response.text
                content = self._extract_text_from_html(html)
                title = self._extract_title(html)
                pages.append({"page_url": current, "title": title, "content": content})

                for link in self._extract_internal_links(current, html, origin):
                    if link not in seen and link not in to_visit and len(seen) + len(to_visit) < source.max_pages:
                        to_visit.append(link)

        return pages

    @staticmethod
    def _normalize_url(raw: str) -> str:
        url = (raw or "").strip()
        if not url:
            return url
        if not url.startswith(("http://", "https://")):
            url = f"https://{url}"
        return url.rstrip("/")

    @staticmethod
    def _extract_title(html: str) -> str | None:
        match = re.search(r"<title>(.*?)</title>", html, flags=re.IGNORECASE | re.DOTALL)
        if not match:
            return None
        return re.sub(r"\s+", " ", match.group(1)).strip()[:512]

    @staticmethod
    def _extract_text_from_html(html: str) -> str:
        no_script = re.sub(r"<script[\s\S]*?</script>", " ", html, flags=re.IGNORECASE)
        no_style = re.sub(r"<style[\s\S]*?</style>", " ", no_script, flags=re.IGNORECASE)
        text = re.sub(r"<[^>]+>", " ", no_style)
        text = re.sub(r"\s+", " ", text).strip()
        return text[:3000]

    @staticmethod
    def _extract_internal_links(current_url: str, html: str, origin: str) -> list[str]:
        links = re.findall(r'href=["\']([^"\']+)["\']', html, flags=re.IGNORECASE)
        normalized: list[str] = []
        seen: set[str] = set()
        for raw_link in links:
            if raw_link.startswith(("mailto:", "tel:", "javascript:", "#")):
                continue
            full_url = urljoin(current_url, raw_link)
            full_url, _ = urldefrag(full_url)
            parsed = urlparse(full_url)
            if parsed.scheme not in {"http", "https"}:
                continue
            if parsed.netloc != origin:
                continue
            cleaned = full_url.rstrip("/")
            if cleaned not in seen:
                seen.add(cleaned)
                normalized.append(cleaned)
        return normalized
