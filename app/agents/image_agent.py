"""Image generation via Pollinations.ai — completely free, no API key required.

How it works:
  Pollinations.ai uses a URL-based API. You construct a URL with your prompt
  and the image is generated on-demand when the URL is accessed. The URL
  itself is the image — suitable for storing as image_url on a post and
  passing directly to the Meta Graph API.

  URL format:
    https://image.pollinations.ai/prompt/{encoded_prompt}?model=flux&width=1024&height=1024

  Docs: https://pollinations.ai
"""

import random
import urllib.parse

from app.core.config import get_settings
from app.core.logging import logger

settings = get_settings()

BASE_URL = "https://image.pollinations.ai/prompt"


class ImageAgent:
    """Generates social-media-ready image URLs via Pollinations.ai."""

    def __init__(self):
        self.enabled = settings.image_generation_enabled
        self.model = settings.pollinations_model
        self.width = settings.pollinations_width
        self.height = settings.pollinations_height

    def generate_image_url(
        self,
        prompt: str,
        width: int | None = None,
        height: int | None = None,
        seed: int | None = None,
    ) -> str | None:
        """Build a Pollinations.ai image URL from a text prompt.

        The returned URL resolves directly to a generated image (JPEG).
        No HTTP call is made here — the image is generated lazily when
        the URL is first accessed (e.g. by the Meta API during publishing).

        Args:
            prompt: Text description of the desired image.
            width:  Image width in pixels (defaults to env setting).
            height: Image height in pixels (defaults to env setting).
            seed:   Optional fixed seed for reproducibility.

        Returns:
            A fully-formed image URL string, or None if generation is disabled
            or the prompt is empty.
        """
        if not self.enabled:
            logger.debug("Image generation is disabled (IMAGE_GENERATION_ENABLED=false)")
            return None

        if not prompt or not prompt.strip():
            logger.warning("Skipping image generation — empty prompt")
            return None

        w = width or self.width
        h = height or self.height
        s = seed if seed is not None else random.randint(1, 999999)

        # Social media optimised prompt suffix
        enhanced_prompt = (
            f"{prompt.strip()}, social media post image, "
            "professional photography, vibrant colors, high quality, 4k"
        )

        encoded = urllib.parse.quote(enhanced_prompt, safe="")
        url = (
            f"{BASE_URL}/{encoded}"
            f"?model={self.model}"
            f"&width={w}"
            f"&height={h}"
            f"&seed={s}"
            f"&nologo=true"
        )

        logger.info(f"Generated image URL (seed={s}): {url[:80]}...")
        return url

    def generate_for_post_type(self, prompt: str, post_type: str) -> str | None:
        """Generate an image URL with dimensions suited to the post type.

        Aspect ratios:
          - promotional / announcement: landscape 1200x628 (Facebook link preview)
          - educational / quote:        square 1080x1080 (Instagram standard)
          - engagement:                 portrait 1080x1350 (Instagram portrait)
        """
        dimension_map = {
            "promotional":   (1200, 628),
            "announcement":  (1200, 628),
            "educational":   (1080, 1080),
            "quote":         (1080, 1080),
            "engagement":    (1080, 1350),
        }
        w, h = dimension_map.get(post_type, (1080, 1080))
        return self.generate_image_url(prompt, width=w, height=h)
