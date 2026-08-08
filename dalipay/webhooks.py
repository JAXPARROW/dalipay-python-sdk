"""Webhook verification utilities for Dalipay SDK."""

import hashlib
import hmac

from .exceptions import WebhookVerificationError
from .models import WebhookPayload


class WebhookHandler:
    """
    Webhook handler for verifying and parsing Dalipay webhooks.

    Every delivery includes an `X-Signature` header - an HMAC-SHA256 of the
    raw request body, signed with your callback secret (shown alongside
    your Webhook URL in Settings).

    Args:
        callback_secret: Your callback secret from Settings

    Usage:
        >>> from dalipay import WebhookHandler
        >>> handler = WebhookHandler("your_callback_secret")
        >>>
        >>> # In your webhook endpoint
        >>> payload = handler.verify_and_parse(
        ...     body=request.body.decode(),
        ...     signature=request.headers["X-Signature"],
        ... )
    """

    def __init__(self, callback_secret: str):
        """
        Initialize webhook handler.

        Args:
            callback_secret: Your callback secret from Settings
        """
        self.callback_secret = callback_secret

    def compute_signature(self, body: str) -> str:
        """
        Compute the expected HMAC-SHA256 signature for a raw request body.

        Args:
            body: Raw request body as string

        Returns:
            Hex-encoded HMAC-SHA256 signature

        Example:
            >>> signature = handler.compute_signature('{"event":"collection.success"}')
        """
        signature = hmac.new(
            self.callback_secret.encode(),
            body.encode(),
            hashlib.sha256,
        )
        return signature.hexdigest()

    def verify_signature(self, body: str, signature: str) -> bool:
        """
        Verify a webhook signature.

        Args:
            body: Raw request body as string
            signature: Value from the X-Signature header

        Returns:
            True if the signature is valid

        Raises:
            WebhookVerificationError: If the signature is invalid

        Example:
            >>> try:
            ...     handler.verify_signature(
            ...         body=request.body.decode(),
            ...         signature=request.headers["X-Signature"],
            ...     )
            ...     print("Webhook verified")
            ... except WebhookVerificationError as e:
            ...     print(f"Verification failed: {e}")
        """
        expected = self.compute_signature(body)
        if not hmac.compare_digest(expected, signature):
            raise WebhookVerificationError("Invalid signature")
        return True

    def parse(self, data: dict) -> WebhookPayload:
        """
        Parse webhook payload without verification.

        Use this if you've already verified the signature separately.

        Args:
            data: Parsed JSON payload from webhook

        Returns:
            WebhookPayload object with typed fields

        Example:
            >>> data = json.loads(request.body)
            >>> payload = handler.parse(data)
            >>> print(payload.event, payload.data.reference)
        """
        return WebhookPayload.from_dict(data)

    def verify_and_parse(self, body: str, signature: str) -> WebhookPayload:
        """
        Verify signature and parse webhook payload in one step.

        This is the main method you'll use in your webhook endpoint.

        Args:
            body: Raw request body as string
            signature: Value from the X-Signature header

        Returns:
            WebhookPayload object

        Raises:
            WebhookVerificationError: If the signature is invalid

        Example:
            >>> from dalipay import WebhookHandler
            >>>
            >>> handler = WebhookHandler("your_callback_secret")
            >>>
            >>> # In your Flask/FastAPI/Django endpoint
            >>> @app.post("/webhooks/dalipay")
            ... def webhook(request):
            ...     try:
            ...         payload = handler.verify_and_parse(
            ...             body=request.body.decode(),
            ...             signature=request.headers["X-Signature"],
            ...         )
            ...
            ...         if payload.event == "collection.success":
            ...             # Mark payload.data.external_id as paid
            ...             pass
            ...
            ...         return {"received": True}
            ...
            ...     except WebhookVerificationError as e:
            ...         return {"error": str(e)}, 401
        """
        import json

        self.verify_signature(body, signature)
        data = json.loads(body)
        return self.parse(data)


def verify_webhook(
    body: str,
    signature: str,
    callback_secret: str,
) -> WebhookPayload:
    """
    Convenience function to verify and parse a webhook.

    This is a one-liner alternative to using the WebhookHandler class.

    Args:
        body: Raw request body as string
        signature: Value from the X-Signature header
        callback_secret: Your callback secret from Settings

    Returns:
        WebhookPayload object

    Raises:
        WebhookVerificationError: If the signature is invalid

    Example:
        >>> from dalipay import verify_webhook, WebhookVerificationError
        >>>
        >>> try:
        ...     payload = verify_webhook(
        ...         body=request.body.decode(),
        ...         signature=request.headers["X-Signature"],
        ...         callback_secret="your_callback_secret",
        ...     )
        ...
        ...     if payload.event == "collection.success":
        ...         print(f"Collection {payload.data.reference} succeeded!")
        ...
        ... except WebhookVerificationError as e:
        ...     print(f"Invalid webhook: {e}")
    """
    handler = WebhookHandler(callback_secret)
    return handler.verify_and_parse(body, signature)
