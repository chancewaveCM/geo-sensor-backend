"""Email notification service using SendGrid."""

import logging
from datetime import UTC, datetime

from app.core.config import settings

logger = logging.getLogger(__name__)


class EmailSender:
    """Email notification service.

    Currently configured for SendGrid but abstracted for easy provider swap.
    """

    def __init__(self, api_key: str | None = None):
        """Initialize email sender with API key."""
        self.api_key = api_key or getattr(settings, "SENDGRID_API_KEY", None)
        if not self.api_key:
            logger.warning("SendGrid API key not configured")

    async def send_notification(
        self,
        to_email: str,
        subject: str,
        body: str,
        html_body: str | None = None,
    ) -> tuple[bool, str | None]:
        """Send email notification.

        Args:
            to_email: Recipient email address
            subject: Email subject
            body: Plain text email body
            html_body: Optional HTML email body

        Returns:
            Tuple of (success: bool, error_message: str | None)
        """
        if not self.api_key:
            error_msg = "SendGrid API key not configured"
            logger.error(error_msg)
            return False, error_msg

        try:
            # TODO: Implement actual SendGrid integration
            # from sendgrid import SendGridAPIClient
            # from sendgrid.helpers.mail import Mail
            #
            # message = Mail(
            #     from_email=settings.SENDER_EMAIL,
            #     to_emails=to_email,
            #     subject=subject,
            #     plain_text_content=body,
            #     html_content=html_body or body
            # )
            # sg = SendGridAPIClient(self.api_key)
            # response = sg.send(message)
            # return response.status_code == 202, None

            # Mock implementation for now
            logger.info(
                "Email notification sent to %s: %s",
                to_email,
                subject,
            )
            return True, None

        except Exception as e:
            error_msg = f"Failed to send email: {e!s}"
            logger.exception(error_msg)
            return False, error_msg

    async def send_campaign_alert(
        self,
        to_email: str,
        campaign_name: str,
        event_type: str,
        details: dict,
    ) -> tuple[bool, str | None]:
        """Send campaign alert email.

        Args:
            to_email: Recipient email address
            campaign_name: Name of the campaign
            event_type: Type of event that triggered the alert
            details: Additional event details

        Returns:
            Tuple of (success: bool, error_message: str | None)
        """
        subject = f"GEO Sensor Alert: {campaign_name} - {event_type}"
        body = f"""
Campaign: {campaign_name}
Event: {event_type}
Time: {datetime.now(tz=UTC).isoformat()}

Details:
{self._format_details(details)}

---
GEO Sensor Notification System
        """.strip()

        return await self.send_notification(to_email, subject, body)

    def _format_details(self, details: dict) -> str:
        """Format details dictionary as readable text."""
        lines = []
        for key, value in details.items():
            lines.append(f"  {key}: {value}")
        return "\n".join(lines) if lines else "  No additional details"
