"""Content strategy agent for planning content calendars."""

import json
from openai import AsyncOpenAI

from app.core.config import get_settings
from app.core.logging import logger
from app.prompts.templates import SYSTEM_PROMPT, CONTENT_STRATEGY_PROMPT

settings = get_settings()


class StrategyAgent:
    """Plans content strategy and generates content calendars."""

    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)
        self.model = settings.openai_model

    async def generate_strategy(
        self,
        platform: str = "facebook",
        niche: str = "general",
        goal: str = "engagement",
        timeframe: str = "1 week",
    ) -> dict:
        """Generate a content strategy for the given parameters."""
        prompt = CONTENT_STRATEGY_PROMPT.format(
            platform=platform,
            niche=niche,
            goal=goal,
            timeframe=timeframe,
        )

        logger.info(f"Generating content strategy for {platform} ({niche})")

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.7,
                max_tokens=2000,
                response_format={"type": "json_object"},
            )

            content = response.choices[0].message.content
            result = json.loads(content)
            logger.info("Content strategy generated successfully")
            return result

        except Exception as e:
            logger.error(f"Strategy generation failed: {e}")
            return {"error": str(e), "posts": []}
