"""Unit tests for WebhookSender SSRF validation."""

import pytest

from app.services.notification.webhook_sender import WebhookSender


class TestWebhookSSRFValidation:
    """Tests for SSRF validation in webhook URLs."""

    def test_blocks_localhost(self) -> None:
        """Test that localhost is blocked."""
        sender = WebhookSender()

        with pytest.raises(ValueError, match="cannot target localhost"):
            sender._validate_webhook_url("http://localhost/api/webhook")

    def test_blocks_127_0_0_1(self) -> None:
        """Test that 127.0.0.1 is blocked."""
        sender = WebhookSender()

        with pytest.raises(ValueError, match="cannot target localhost"):
            sender._validate_webhook_url("http://127.0.0.1/api/webhook")

    def test_blocks_ipv6_loopback(self) -> None:
        """Test that ::1 (IPv6 loopback) is blocked."""
        sender = WebhookSender()

        with pytest.raises(ValueError, match="cannot target localhost"):
            sender._validate_webhook_url("http://[::1]/api/webhook")

    def test_blocks_0_0_0_0(self) -> None:
        """Test that 0.0.0.0 is blocked."""
        sender = WebhookSender()

        with pytest.raises(ValueError, match="cannot target localhost"):
            sender._validate_webhook_url("http://0.0.0.0/api/webhook")

    def test_blocks_private_ip_192_168(self) -> None:
        """Test that private IP 192.168.x.x is blocked."""
        sender = WebhookSender()

        with pytest.raises(ValueError, match="cannot target private IP"):
            sender._validate_webhook_url("http://192.168.1.1/webhook")

    def test_blocks_private_ip_10_0(self) -> None:
        """Test that private IP 10.x.x.x is blocked."""
        sender = WebhookSender()

        with pytest.raises(ValueError, match="cannot target private IP"):
            sender._validate_webhook_url("http://10.0.0.1/webhook")

    def test_blocks_private_ip_172_16(self) -> None:
        """Test that private IP 172.16.x.x is blocked."""
        sender = WebhookSender()

        with pytest.raises(ValueError, match="cannot target private IP"):
            sender._validate_webhook_url("http://172.16.0.1/webhook")

    def test_allows_valid_external_url(self) -> None:
        """Test that valid external HTTPS URL is allowed."""
        sender = WebhookSender()

        # Should not raise
        sender._validate_webhook_url("https://hooks.slack.com/services/xxx")

    def test_allows_valid_http_url(self) -> None:
        """Test that valid external HTTP URL is allowed."""
        sender = WebhookSender()

        # Should not raise
        sender._validate_webhook_url("http://example.com/webhook")

    def test_blocks_ftp_scheme(self) -> None:
        """Test that non-HTTP scheme (ftp://) is blocked."""
        sender = WebhookSender()

        with pytest.raises(ValueError, match="must use HTTP or HTTPS"):
            sender._validate_webhook_url("ftp://example.com/file")

    def test_blocks_file_scheme(self) -> None:
        """Test that file:// scheme is blocked."""
        sender = WebhookSender()

        with pytest.raises(ValueError, match="must use HTTP or HTTPS"):
            sender._validate_webhook_url("file:///etc/passwd")

    def test_allows_https(self) -> None:
        """Test that HTTPS is explicitly allowed."""
        sender = WebhookSender()

        # Should not raise
        sender._validate_webhook_url("https://api.example.com/webhook")

    def test_domain_names_are_allowed(self) -> None:
        """Test that domain names (not IPs) are allowed."""
        sender = WebhookSender()

        # Domain names should pass (not caught by IP checks)
        sender._validate_webhook_url("https://webhook.site/unique-id")
        sender._validate_webhook_url("https://discord.com/api/webhooks/123")

    def test_blocks_link_local_ip(self) -> None:
        """Test that link-local IPs (169.254.x.x) are blocked."""
        sender = WebhookSender()

        with pytest.raises(ValueError, match="cannot target private IP"):
            sender._validate_webhook_url("http://169.254.1.1/webhook")
