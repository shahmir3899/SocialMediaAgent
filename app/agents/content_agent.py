"""AI-powered content generation agent.

Supports three providers via environment configuration:
  - groq   (default) — fast, free tier, Llama models
  - ollama            — fully local, no API key needed
  - openai            — GPT-4 / GPT-4o
"""

import json
import re
from openai import AsyncOpenAI

from app.core.config import get_settings
from app.core.logging import logger
from app.prompts.templates import SYSTEM_PROMPT, POST_GENERATION_PROMPT

settings = get_settings()

# Ollama does not enforce JSON output mode via response_format on all models.
# For Ollama we instead inject a JSON instruction into the prompt and parse freeform.
_PROVIDERS_WITH_JSON_MODE = {"groq", "openai"}


def _resolve_api_key() -> str:
    """Return the correct API key for the configured provider."""
    if settings.ai_provider == "ollama":
        return "ollama"
    if settings.ai_provider == "groq":
        # Prefer GROQ_API_KEY; fall back to OPENAI_API_KEY for backwards compat
        return settings.groq_api_key or settings.openai_api_key
    return settings.openai_api_key


def _resolve_model() -> str:
    """Return the correct model name for the configured provider."""
    if settings.ai_provider == "groq":
        return settings.groq_model or settings.openai_model
    return settings.openai_model


def _build_client() -> AsyncOpenAI:
    """Build an AsyncOpenAI-compatible client for the configured provider."""
    api_key = _resolve_api_key()

    if settings.ai_provider == "ollama":
        return AsyncOpenAI(
            api_key=api_key,
            base_url=settings.ai_base_url or "http://localhost:11434/v1",
        )

    if settings.ai_provider == "groq" or settings.ai_base_url:
        return AsyncOpenAI(
            api_key=api_key,
            base_url=settings.ai_base_url,
        )

    # Default: standard OpenAI
    return AsyncOpenAI(api_key=api_key)


def _extract_json(text: str) -> dict:
    """Extract a JSON object from a text string, even if wrapped in markdown fences."""
    # Try direct parse first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Strip ```json ... ``` fences that some models emit
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if match:
        return json.loads(match.group(1))

    # Last resort: find first {...} block
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        return json.loads(match.group(0))

    raise ValueError("No JSON object found in response")


class ContentAgent:
    """Generates social media content using a configurable LLM provider."""

    def __init__(self):
        self.client = _build_client()
        self.model = _resolve_model()
        self.provider = settings.ai_provider
        self._use_json_mode = self.provider in _PROVIDERS_WITH_JSON_MODE
        logger.info(
            f"ContentAgent initialised — provider={self.provider} "
            f"model={self.model} json_mode={self._use_json_mode}"
        )

    async def generate_post(
        self,
        post_type: str = "educational",
        platform: str = "facebook",
        topic: str | None = None,
    ) -> dict:
        """Generate a single social media post.

        Returns:
            dict with keys: caption, hashtags, image_prompt, post_type
        """
        topic_instruction = f"Topic/theme: {topic}" if topic else "Choose a relevant trending topic."

        prompt = POST_GENERATION_PROMPT.format(
            post_type=post_type,
            platform=platform,
            topic_instruction=topic_instruction,
        )

        # For Ollama (no JSON mode), reinforce the format requirement in the prompt
        if not self._use_json_mode:
            prompt += "\n\nIMPORTANT: Your entire response must be a single valid JSON object. No extra text before or after."

        logger.info(f"Generating {post_type} post for {platform} via {self.provider}")

        try:
            kwargs = dict(
                model=self.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                temperature=1.0,
                max_tokens=1000,
            )

            if self._use_json_mode:
                kwargs["response_format"] = {"type": "json_object"}

            response = await self.client.chat.completions.create(**kwargs)
            raw = response.choices[0].message.content
            result = _extract_json(raw)

            logger.info(f"Generated post: {result.get('caption', '')[:60]}...")
            return {
                "caption": result.get("caption", ""),
                "hashtags": result.get("hashtags", []),
                "image_prompt": result.get("image_prompt", ""),
                "post_type": result.get("post_type", post_type),
            }

        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Failed to parse LLM response as JSON: {e}")
            return self._fallback_post(post_type)
        except Exception as e:
            logger.error(f"Content generation failed [{self.provider}]: {e}")
            return self._fallback_post(post_type)

    async def generate_batch(
        self,
        post_types: list[str],
        platform: str = "facebook",
    ) -> list[dict]:
        """Generate multiple posts sequentially."""
        results = []
        for pt in post_types:
            result = await self.generate_post(post_type=pt, platform=platform)
            results.append(result)
        return results

    @staticmethod
    def _fallback_post(post_type: str) -> dict:
        """Return a safe placeholder when generation fails."""
        return {
            "caption": f"[Generation failed] Placeholder {post_type} post — edit before publishing.",
            "hashtags": ["socialmedia", "content"],
            "image_prompt": "A simple branded graphic",
            "post_type": post_type,
        }
