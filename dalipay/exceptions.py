"""Exceptions for Dalipay SDK."""


class DalipayError(Exception):
    """Base exception for all Dalipay errors.

    All exceptions raised by the SDK inherit from this class.

    Args:
        message: Human-readable error description (from the API's `message` field)
        code: HTTP status code from the API response

    Example:
        >>> from dalipay import DalipayError
        >>> try:
        ...     client.create_collection(...)
        ... except DalipayError as e:
        ...     print(f"Error: {e.message}")
        ...     print(f"HTTP Code: {e.code}")

    """

    def __init__(self, message: str, code: int = 0):
        self.message = message
        self.code = code
        super().__init__(message)


class ValidationError(DalipayError):
    """Bad request (400) - missing/invalid field, malformed JSON, etc."""
    pass


class AuthenticationError(DalipayError):
    """Missing or invalid X-Public-Key / X-Secret-Key (401)."""
    pass


class PaymentRequiredError(DalipayError):
    """Insufficient balance for a disbursement/settlement (402)."""
    pass


class ForbiddenError(DalipayError):
    """Request IP not whitelisted, or KYC required for production (403)."""
    pass


class NotFoundError(DalipayError):
    """Unknown collection/disbursement UUID or reference for this merchant (404)."""
    pass


class MethodNotAllowedError(DalipayError):
    """Wrong HTTP verb for the endpoint (405)."""
    pass


class ServerError(DalipayError):
    """Unexpected internal error (500)."""
    pass


class WebhookVerificationError(DalipayError):
    """Invalid webhook signature."""
    pass
