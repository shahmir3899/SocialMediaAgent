"""Prompt templates for AI content generation."""

SYSTEM_PROMPT = """You are a professional social media content strategist.
You create engaging, platform-optimized posts that drive engagement.
Always respond in valid JSON format."""

POST_GENERATION_PROMPT = """Generate a {post_type} social media post for {platform}.

{topic_instruction}

Requirements:
- Caption should be engaging, concise, and platform-appropriate
- Include 3-5 relevant hashtags
- Suggest an image concept that would complement the post
- Facebook posts can be longer (up to 300 words), Instagram should be concise (under 150 words)

Post type guidelines:
- educational: Share valuable knowledge, tips, or how-to content
- engagement: Ask questions, create polls, encourage comments
- promotional: Highlight products/services with a clear CTA
- quote: Share an inspirational or thought-provoking quote
- announcement: Share news or updates

Respond in this exact JSON format:
{{
    "caption": "Your caption text here",
    "hashtags": ["hashtag1", "hashtag2", "hashtag3"],
    "image_prompt": "Description of an ideal image for this post",
    "post_type": "{post_type}"
}}"""

CONTENT_STRATEGY_PROMPT = """Create a content strategy for the following parameters:

Platform: {platform}
Niche: {niche}
Goal: {goal}
Timeframe: {timeframe}

Generate a content calendar with post ideas including:
1. Post types mix
2. Posting schedule
3. Content themes
4. Engagement strategies

Respond in JSON format with an array of post ideas."""
