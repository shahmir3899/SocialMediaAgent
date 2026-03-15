"""Image caching utility — downloads Pollinations.ai on-demand images
and stores them locally so the dashboard can serve them instantly."""

import os
import httpx
from pathlib import Path

from app.core.logging import logger

# Persistent cache directory — mounted as a Docker volume in production
CACHE_DIR = Path(os.environ.get("IMAGE_CACHE_DIR", "uploads/images"))

# Keep timeout bounded to avoid gateway 504s when upstream is unhealthy.
_TIMEOUT = httpx.Timeout(35.0, connect=8.0)


def _ensure_cache_dir() -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)


def cached_path(post_id: int) -> Path:
    """Return the expected file path for a cached post image."""
    return CACHE_DIR / f"{post_id}.jpg"


def is_cached(post_id: int) -> bool:
    """Check whether a cached image already exists for this post."""
    p = cached_path(post_id)
    return p.exists() and p.stat().st_size > 1000


async def download_and_cache(post_id: int, image_url: str) -> bool:
    """Download an image from *image_url* and cache it on disk.

    Returns True on success, False on failure.
    """
    _ensure_cache_dir()
    dest = cached_path(post_id)

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT, follow_redirects=True) as client:
            logger.info(f"[image_cache] Downloading post {post_id}: {image_url[:80]}...")
            resp = await client.get(image_url)
            if resp.status_code == 200 and len(resp.content) > 1000:
                dest.write_bytes(resp.content)
                logger.info(f"[image_cache] Cached post {post_id}: {len(resp.content)} bytes")
                return True
            logger.warning(
                f"[image_cache] Bad response for post {post_id}: "
                f"status={resp.status_code} size={len(resp.content)}"
            )
            return False
    except Exception as e:
        logger.error(f"[image_cache] Download failed for post {post_id}: {e}")
        return False
