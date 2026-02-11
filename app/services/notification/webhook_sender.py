"""Webhook notification service with HMAC signing."""

import hashlib
import hmac
import json
import logging
from datetime import UTC, datetime

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class WebhookSender:
    """Webhook notification service with HMAC signature verification."""

    def __init__(self, secret_key: str | None = None):
        """Initialize webhook sender with signing secret."""
        self.secret_key = secret_key or getattr(settings, "WEBHOOK_SECRET_KEY", None)
        if not self.secret_key:
            logger.warning("Webhook secret key not configured")

    def _generate_signature(self, payload: str) -> str:
        """Generate HMAC-SHA256 signature for payload."""
        if not self.secret_key:
            return ""
        signature = hmac.new(
            self.secret_key.encode(),
            payload.encode(),
            hashlib.sha256,
        ).hexdigest()
        return f"sha256={signature}"

    async def send_notification(
        self,
        webhook_url: str,
        payload: dict,
        timeout: int = 30,
    ) -> tuple[bool, str | None]:
        """Send webhook notification with HMAC signature.

        Args:
            webhook_url: Target webhook URL
            payload: JSON payload to send
            timeout: Request timeout in seconds

        Returns:
            Tuple of (success: bool, error_message: str | None)
        """
        try:
            payload_str = json.dumps(payload)
            signature = self._generate_signature(payload_str)

            headers = {
                "Content-Type": "application/json",
                "User-Agent": "GEO-Sensor-Webhook/1.0",
                "X-GEO-Signature": signature,
                "X-GEO-Timestamp": datetime.now(tz=UTC).isoformat(),
            }

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    webhook_url,
                    content=payload_str,
                    headers=headers,
                    timeout=timeout,
                )
                response.raise_for_status()

            logger.info(
                "Webhook notification sent to %s (status: %d)",
                webhook_url,
                response.status_code,
            )
            return True, None

        except httpx.HTTPStatusError as e:
            error_msg = f"Webhook returned {e.response.status_code}: {e.response.text}"
            logger.error(error_msg)
            return False, error_msg

        except httpx.RequestError as e:
            error_msg = f"Failed to send webhook: {e!s}"
            logger.error(error_msg)
            return False, error_msg

        except Exception as e:
            error_msg = f"Unexpected error sending webhook: {e!s}"
            logger.exception(error_msg)
            return False, error_msg

    async def send_campaign_alert(
        self,
        webhook_url: str,
        campaign_id: int,
        campaign_name: str,
        event_type: str,
        details: dict,
    ) -> tuple[bool, str | None]:
        """Send campaign alert via webhook.

        Args:
            webhook_url: Target webhook URL
            campaign_id: Campaign ID
            campaign_name: Name of the campaign
            event_type: Type of event that triggered the alert
            details: Additional event details

        Returns:
            Tuple of (success: bool, error_message: str | None)
        """
        payload = {
            "event": "campaign_alert",
            "timestamp": datetime.now(tz=UTC).isoformat(),
            "campaign": {
                "id": campaign_id,
                "name": campaign_name,
            },
            "alert": {
                "type": event_type,
                "details": details,
            },
        }

        return await self.send_notification(webhook_url, payload)
