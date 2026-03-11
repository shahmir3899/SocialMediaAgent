"""Meta (Facebook/Instagram) Graph API client."""

import httpx
from app.core.config import get_settings
from app.core.logging import logger

settings = get_settings()

BASE_URL = f"https://graph.facebook.com/{settings.facebook_graph_api_version}"


class MetaClient:
    """Client for interacting with Facebook and Instagram Graph APIs."""

    def __init__(self):
        self.base_url = BASE_URL
        self.timeout = httpx.Timeout(30.0)

    async def validate_token(self, access_token: str) -> bool:
        """Validate an access token with the Meta API."""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    f"{self.base_url}/debug_token",
                    params={
                        "input_token": access_token,
                        "access_token": f"{settings.meta_app_id}|{settings.meta_app_secret}",
                    },
                )
                data = response.json()
                is_valid = data.get("data", {}).get("is_valid", False)
                logger.info(f"Token validation result: {is_valid}")
                return is_valid
        except Exception as e:
            logger.error(f"Token validation failed: {e}")
            return False

    async def publish_facebook_post(
        self, page_id: str, access_token: str, message: str, image_url: str | None = None
    ) -> dict:
        """Publish a post to a Facebook Page."""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                if image_url:
                    # Photo post
                    endpoint = f"{self.base_url}/{page_id}/photos"
                    payload = {
                        "message": message,
                        "url": image_url,
                        "access_token": access_token,
                    }
                else:
                    # Text post
                    endpoint = f"{self.base_url}/{page_id}/feed"
                    payload = {
                        "message": message,
                        "access_token": access_token,
                    }

                response = await client.post(endpoint, data=payload)
                result = response.json()

                if "error" in result:
                    logger.error(f"Facebook publish error: {result['error']}")
                    return {"success": False, "error": result["error"], "response": result}

                logger.info(f"Published to Facebook page {page_id}: {result.get('id')}")
                return {"success": True, "post_id": result.get("id"), "response": result}

        except Exception as e:
            logger.error(f"Facebook publish failed: {e}")
            return {"success": False, "error": str(e)}

    async def publish_instagram_post(
        self, ig_user_id: str, access_token: str, caption: str, image_url: str
    ) -> dict:
        """Publish a post to Instagram (requires image_url).

        Instagram publishing is a two-step process:
        1. Create a media container
        2. Publish the container
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                # Step 1: Create media container
                container_response = await client.post(
                    f"{self.base_url}/{ig_user_id}/media",
                    data={
                        "image_url": image_url,
                        "caption": caption,
                        "access_token": access_token,
                    },
                )
                container_data = container_response.json()

                if "error" in container_data:
                    logger.error(f"Instagram container creation error: {container_data['error']}")
                    return {"success": False, "error": container_data["error"]}

                creation_id = container_data.get("id")

                # Step 2: Publish the container
                publish_response = await client.post(
                    f"{self.base_url}/{ig_user_id}/media_publish",
                    data={
                        "creation_id": creation_id,
                        "access_token": access_token,
                    },
                )
                publish_data = publish_response.json()

                if "error" in publish_data:
                    logger.error(f"Instagram publish error: {publish_data['error']}")
                    return {"success": False, "error": publish_data["error"]}

                logger.info(f"Published to Instagram: {publish_data.get('id')}")
                return {"success": True, "post_id": publish_data.get("id"), "response": publish_data}

        except Exception as e:
            logger.error(f"Instagram publish failed: {e}")
            return {"success": False, "error": str(e)}

    async def upload_media(self, page_id: str, access_token: str, image_url: str) -> dict:
        """Upload media to a Facebook Page for later use."""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/{page_id}/photos",
                    data={
                        "url": image_url,
                        "published": "false",
                        "access_token": access_token,
                    },
                )
                result = response.json()

                if "error" in result:
                    logger.error(f"Media upload error: {result['error']}")
                    return {"success": False, "error": result["error"]}

                logger.info(f"Media uploaded: {result.get('id')}")
                return {"success": True, "media_id": result.get("id"), "response": result}

        except Exception as e:
            logger.error(f"Media upload failed: {e}")
            return {"success": False, "error": str(e)}

    async def get_page_info(self, page_id: str, access_token: str) -> dict:
        """Get information about a Facebook Page."""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    f"{self.base_url}/{page_id}",
                    params={
                        "fields": "id,name,category,fan_count",
                        "access_token": access_token,
                    },
                )
                return response.json()
        except Exception as e:
            logger.error(f"Failed to get page info: {e}")
            return {"error": str(e)}

    async def exchange_code_for_token(self, code: str) -> dict:
        """Exchange an authorization code for a short-lived user access token."""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    "https://graph.facebook.com/oauth/access_token",
                    params={
                        "client_id": settings.meta_app_id,
                        "client_secret": settings.meta_app_secret,
                        "redirect_uri": settings.meta_redirect_uri,
                        "code": code,
                    },
                )
                data = response.json()
                if "error" in data:
                    logger.error(f"Code exchange error: {data['error']}")
                    return {}
                return data
        except Exception as e:
            logger.error(f"Code exchange failed: {e}")
            return {}

    async def exchange_for_long_lived_token(self, short_lived_token: str) -> dict:
        """Exchange a short-lived user token for a 60-day long-lived token."""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    "https://graph.facebook.com/oauth/access_token",
                    params={
                        "grant_type": "fb_exchange_token",
                        "client_id": settings.meta_app_id,
                        "client_secret": settings.meta_app_secret,
                        "fb_exchange_token": short_lived_token,
                    },
                )
                data = response.json()
                if "error" in data:
                    logger.error(f"Long-lived token exchange error: {data['error']}")
                    return {}
                return data
        except Exception as e:
            logger.error(f"Long-lived token exchange failed: {e}")
            return {}

    async def get_managed_pages(self, user_access_token: str) -> list[dict]:
        """Get all Facebook Pages managed by the authenticated user."""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    f"{self.base_url}/me/accounts",
                    params={
                        "access_token": user_access_token,
                        "fields": "id,name,access_token,category",
                    },
                )
                data = response.json()
                if "error" in data:
                    logger.error(f"Get managed pages error: {data['error']}")
                    return []
                return data.get("data", [])
        except Exception as e:
            logger.error(f"Get managed pages failed: {e}")
            return []

    async def get_instagram_account(self, page_id: str, page_access_token: str) -> dict | None:
        """Get the Instagram Business Account linked to a Facebook Page, or None."""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    f"{self.base_url}/{page_id}",
                    params={
                        "fields": "instagram_business_account",
                        "access_token": page_access_token,
                    },
                )
                data = response.json()
                if "error" in data:
                    logger.debug(f"No Instagram account for page {page_id}")
                    return None
                return data.get("instagram_business_account")
        except Exception as e:
            logger.error(f"Get Instagram account failed: {e}")
            return None
