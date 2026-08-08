"""Dalipay Collections & Disbursements API client."""

import asyncio
import time
import uuid as uuid_lib
from typing import Optional

import httpx

from .exceptions import (
    AuthenticationError,
    DalipayError,
    ForbiddenError,
    MethodNotAllowedError,
    NotFoundError,
    PaymentRequiredError,
    ServerError,
    ValidationError,
)
from .models import Collection, Disbursement
from .types import Currency, Provider
from .utils import guess_provider


def _resolve_provider(account_number: str, provider: Optional[Provider]) -> Provider:
    """Return `provider` as given, or guess it from `account_number`."""
    resolved = provider or guess_provider(account_number)
    if resolved is None:
        raise ValueError(
            f"Could not determine provider from account_number {account_number!r}; "
            "pass provider explicitly (Tigo, Airtel, Halopesa, Azampesa, or Mpesa)."
        )
    return resolved


class Dalipay:
    """
    Dalipay Collections & Disbursements API client.

    Dalipay is self-hosted per merchant/gateway deployment, so there is no
    single shared API host - pass the base URL for your own gateway
    (e.g. "https://your-gateway-domain/api/v1").

    Usage:
        >>> from dalipay import Dalipay
        >>> client = Dalipay(
        ...     public_key="gw_pk_test_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
        ...     secret_key="gw_sk_test_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
        ...     base_url="https://your-gateway-domain/api/v1",
        ... )
        >>> collection = client.create_collection(
        ...     account_number="0712345678",
        ...     amount=1000,
        ...     provider="Tigo",
        ...     external_id="INV-00123",
        ... )

    Args:
        public_key: Your X-Public-Key (gw_pk_test_... or gw_pk_production_...)
        secret_key: Your X-Secret-Key (gw_sk_test_... or gw_sk_production_...)
        base_url: Your gateway's base URL, e.g. "https://your-gateway-domain/api/v1"
        timeout: Request timeout in seconds (default: 30.0)

    Only call this from your backend - never from a browser, mobile app, or
    any client the public can inspect. If a key pair is exposed, revoke it
    immediately and generate a new one.

    Example with context manager:
        >>> with Dalipay(public_key, secret_key, base_url) as client:
        ...     collection = client.create_collection(...)
    """

    def __init__(
        self,
        public_key: str,
        secret_key: str,
        base_url: str,
        timeout: float = 30.0,
    ):
        """
        Initialize Dalipay client.

        Args:
            public_key: Your X-Public-Key
            secret_key: Your X-Secret-Key
            base_url: Your gateway's base URL, e.g. "https://your-gateway-domain/api/v1"
            timeout: Request timeout in seconds
        """
        if not base_url:
            raise ValueError(
                "base_url is required, e.g. https://your-gateway-domain/api/v1"
            )
        self.public_key = public_key
        self.secret_key = secret_key
        self.base_url = base_url
        self._client = httpx.Client(
            base_url=self.base_url,
            headers={
                "X-Public-Key": public_key,
                "X-Secret-Key": secret_key,
                "Content-Type": "application/json",
            },
            timeout=timeout,
        )

    def _handle_response(self, response: httpx.Response) -> dict:
        """Handle API response and raise appropriate exceptions."""
        try:
            data = response.json()
        except Exception:
            data = {"success": False, "message": response.text}

        if data.get("success"):
            return data.get("data", {})

        message = data.get("message", "Unknown error")
        code = response.status_code

        if code == 400:
            raise ValidationError(message, code)
        elif code == 401:
            raise AuthenticationError(message, code)
        elif code == 402:
            raise PaymentRequiredError(message, code)
        elif code == 403:
            raise ForbiddenError(message, code)
        elif code == 404:
            raise NotFoundError(message, code)
        elif code == 405:
            raise MethodNotAllowedError(message, code)
        elif code >= 500:
            raise ServerError(message, code)
        else:
            raise DalipayError(message, code)

    def create_collection(
        self,
        account_number: str,
        amount: float,
        external_id: str,
        provider: Optional[Provider] = None,
        currency: Currency = "TZS",
        customer_name: Optional[str] = None,
    ) -> Collection:
        """
        Trigger a mobile money checkout prompt on the customer's phone.

        The customer confirms or cancels on their device; the final result
        arrives asynchronously - poll `get_collection_status`,
        `wait_for_collection`, or configure a webhook.

        Args:
            account_number: Customer's mobile money number, e.g. 0712345678
            amount: Amount to collect (whole units, e.g. TZS)
            external_id: Your own unique reference for this payment (max 30 chars)
            provider: Tigo, Airtel, Halopesa, Azampesa, or Mpesa - must
                match the customer's network. If omitted, guessed from
                account_number's prefix (see `dalipay.guess_provider`) -
                numbers can be ported between networks, so pass this
                explicitly if you already know the actual carrier.
            currency: Currency code (defaults to TZS)
            customer_name: Customer's name, for your records and receipts

        Returns:
            Collection object with uuid, reference, and status "processing"

        Raises:
            ValueError: provider was omitted and couldn't be guessed from
                account_number (e.g. a 073/TTCL number, which has no
                mobile money provider on this API)

        Example:
            >>> collection = client.create_collection(
            ...     account_number="0712345678",
            ...     amount=1000,
            ...     external_id="INV-00123",
            ...     provider="Tigo",
            ...     customer_name="Asha Mwakasege",
            ... )
            >>> print(collection.uuid)
        """
        resolved_provider = _resolve_provider(account_number, provider)
        payload = {
            "account_number": account_number,
            "amount": amount,
            "currency": currency,
            "provider": resolved_provider,
            "external_id": external_id,
        }
        if customer_name:
            payload["customer_name"] = customer_name

        response = self._client.post("/collections", json=payload)
        data = self._handle_response(response)
        return Collection.from_dict(data)

    def get_collection_status(self, uuid: str) -> Collection:
        """
        Check whether the customer confirmed or cancelled a collection prompt.

        For most integrations, webhooks are faster - use polling as a
        fallback or for an on-demand "refresh" button.

        Args:
            uuid: The collection's uuid, from `create_collection`

        Returns:
            Collection object with current status

        Example:
            >>> collection = client.get_collection_status(collection.uuid)
            >>> if collection.status == "success":
            ...     # Fulfill order
            ...     pass
        """
        response = self._client.get(f"/collections/{uuid}/status")
        data = self._handle_response(response)
        return Collection.from_dict(data)

    def wait_for_collection(
        self,
        uuid: str,
        timeout: float = 300.0,
        interval: float = 3.0,
    ) -> Collection:
        """
        Poll `get_collection_status` until it leaves "processing" or times out.

        Dalipay does not guarantee a fixed resolution window (the docs
        only suggest ~5 minutes as a rule of thumb) and there is no
        automatic retry - a cancelled/declined/expired prompt is terminal
        ("failed"); to try again you must call `create_collection` again
        with a fresh external_id.

        Args:
            uuid: The collection's uuid, from `create_collection`
            timeout: Give up polling after this many seconds (default: 300)
            interval: Seconds to wait between polls (default: 3)

        Returns:
            Collection object - status is "success" or "failed" if it
            resolved in time, or still "processing" if the timeout
            elapsed. This does not raise on timeout - check the returned
            status yourself.

        Example:
            >>> collection = client.create_collection(...)
            >>> result = client.wait_for_collection(collection.uuid)
            >>> if result.status == "success":
            ...     print("Paid!")
            ... elif result.status == "failed":
            ...     print("Cancelled, declined, or expired")
            ... else:
            ...     print("Still processing after the timeout")
        """
        deadline = time.monotonic() + timeout
        collection = self.get_collection_status(uuid)
        while collection.status == "processing" and time.monotonic() < deadline:
            time.sleep(interval)
            collection = self.get_collection_status(uuid)
        return collection

    def create_disbursement(
        self,
        account_number: str,
        amount: float,
        external_id: str,
        provider: Optional[Provider] = None,
        recipient_name: Optional[str] = None,
        remarks: Optional[str] = None,
    ) -> Disbursement:
        """
        Send a payout from your gateway balance to a mobile money account.

        In production, the amount + fee is held from your balance
        immediately and the request waits for platform admin approval
        (status "awaiting_approval"). In test mode it's simulated instantly
        (status "success").

        Args:
            account_number: Recipient's mobile money number
            amount: Amount to send (between 1 and 5,000,000)
            external_id: Your unique reference (max 30 chars)
            provider: Airtel, Tigo, Azampesa, Halopesa, or Mpesa. If
                omitted, guessed from account_number's prefix (see
                `dalipay.guess_provider`) - pass this explicitly if you
                already know the actual carrier.
            recipient_name: Name on the receiving account
            remarks: Free-text note

        Returns:
            Disbursement object with reference and status

        Raises:
            ValueError: provider was omitted and couldn't be guessed from
                account_number

        Example:
            >>> disbursement = client.create_disbursement(
            ...     account_number="0712345678",
            ...     amount=5000,
            ...     external_id="PAYOUT-00045",
            ...     provider="Tigo",
            ...     recipient_name="Juma Hassan",
            ...     remarks="Agent commission",
            ... )
            >>> print(disbursement.reference, disbursement.status)
        """
        resolved_provider = _resolve_provider(account_number, provider)
        payload = {
            "account_number": account_number,
            "amount": amount,
            "provider": resolved_provider,
            "external_id": external_id,
        }
        if recipient_name:
            payload["recipient_name"] = recipient_name
        if remarks:
            payload["remarks"] = remarks

        response = self._client.post("/disbursements", json=payload)
        data = self._handle_response(response)
        return Disbursement.from_dict(data)

    def get_disbursement_status(self, reference: str) -> Disbursement:
        """
        Check the status of a disbursement.

        Args:
            reference: The disbursement's reference, from `create_disbursement`

        Returns:
            Disbursement object with current status

        Example:
            >>> disbursement = client.get_disbursement_status(disbursement.reference)
            >>> print(f"Status: {disbursement.status}")
        """
        response = self._client.get(f"/disbursements/{reference}/status")
        data = self._handle_response(response)
        return Disbursement.from_dict(data)

    def is_healthy(self) -> bool:
        """
        Check that the gateway is reachable and the key pair is valid.

        Dalipay doesn't publish a dedicated health-check endpoint, and
        every documented POST endpoint has real side effects (a USSD
        prompt, a money movement) - so this can't just ping the API. It
        instead does a read-only `GET /collections/{uuid}/status` with a
        randomly generated uuid that's virtually guaranteed not to exist:

        - 404 means the base_url is reachable and the key pair was
          accepted (bad credentials would 401 first) - healthy.
        - 401 means the key pair was rejected - unhealthy.
        - A network error (DNS, connection refused, timeout) - unhealthy.

        No collection or disbursement is created; nothing is sent to any
        phone number.

        Returns:
            True if the gateway is reachable and the credentials are valid.

        Example:
            >>> if not client.is_healthy():
            ...     raise RuntimeError("Cannot reach Dalipay gateway")
        """
        probe_uuid = str(uuid_lib.uuid4())
        try:
            response = self._client.get(f"/collections/{probe_uuid}/status")
        except httpx.RequestError:
            return False

        if response.status_code == 401:
            return False
        return response.status_code < 500

    def close(self) -> None:
        """
        Close the HTTP client.

        Should be called when done using the client to free resources.
        Not needed when using the context manager.

        Example:
            >>> client = Dalipay(public_key, secret_key, base_url)
            >>> # ... do work ...
            >>> client.close()
        """
        self._client.close()

    def __enter__(self) -> "Dalipay":
        return self

    def __exit__(self, *args) -> None:
        self.close()


class AsyncDalipay:
    """
    Async Dalipay Collections & Disbursements API client.

    For use with asyncio-based frameworks like FastAPI, aiohttp, etc.

    Usage:
        >>> from dalipay import AsyncDalipay
        >>> async with AsyncDalipay(public_key, secret_key, base_url) as client:
        ...     collection = await client.create_collection(
        ...         account_number="0712345678",
        ...         amount=1000,
        ...         provider="Tigo",
        ...         external_id="INV-00123",
        ...     )

    Args:
        public_key: Your X-Public-Key
        secret_key: Your X-Secret-Key
        base_url: Your gateway's base URL, e.g. "https://your-gateway-domain/api/v1"
        timeout: Request timeout in seconds (default: 30.0)
    """

    def __init__(
        self,
        public_key: str,
        secret_key: str,
        base_url: str,
        timeout: float = 30.0,
    ):
        """Initialize async Dalipay client."""
        if not base_url:
            raise ValueError(
                "base_url is required, e.g. https://your-gateway-domain/api/v1"
            )
        self.public_key = public_key
        self.secret_key = secret_key
        self.base_url = base_url
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={
                "X-Public-Key": public_key,
                "X-Secret-Key": secret_key,
                "Content-Type": "application/json",
            },
            timeout=timeout,
        )

    async def _handle_response(self, response: httpx.Response) -> dict:
        """Handle API response and raise appropriate exceptions."""
        try:
            data = response.json()
        except Exception:
            data = {"success": False, "message": response.text}

        if data.get("success"):
            return data.get("data", {})

        message = data.get("message", "Unknown error")
        code = response.status_code

        if code == 400:
            raise ValidationError(message, code)
        elif code == 401:
            raise AuthenticationError(message, code)
        elif code == 402:
            raise PaymentRequiredError(message, code)
        elif code == 403:
            raise ForbiddenError(message, code)
        elif code == 404:
            raise NotFoundError(message, code)
        elif code == 405:
            raise MethodNotAllowedError(message, code)
        elif code >= 500:
            raise ServerError(message, code)
        else:
            raise DalipayError(message, code)

    async def create_collection(
        self,
        account_number: str,
        amount: float,
        external_id: str,
        provider: Optional[Provider] = None,
        currency: Currency = "TZS",
        customer_name: Optional[str] = None,
    ) -> Collection:
        """Trigger a mobile money checkout prompt on the customer's phone."""
        resolved_provider = _resolve_provider(account_number, provider)
        payload = {
            "account_number": account_number,
            "amount": amount,
            "currency": currency,
            "provider": resolved_provider,
            "external_id": external_id,
        }
        if customer_name:
            payload["customer_name"] = customer_name

        response = await self._client.post("/collections", json=payload)
        data = await self._handle_response(response)
        return Collection.from_dict(data)

    async def get_collection_status(self, uuid: str) -> Collection:
        """Check whether the customer confirmed or cancelled a collection prompt."""
        response = await self._client.get(f"/collections/{uuid}/status")
        data = await self._handle_response(response)
        return Collection.from_dict(data)

    async def wait_for_collection(
        self,
        uuid: str,
        timeout: float = 300.0,
        interval: float = 3.0,
    ) -> Collection:
        """Async version of `Dalipay.wait_for_collection`."""
        deadline = time.monotonic() + timeout
        collection = await self.get_collection_status(uuid)
        while collection.status == "processing" and time.monotonic() < deadline:
            await asyncio.sleep(interval)
            collection = await self.get_collection_status(uuid)
        return collection

    async def create_disbursement(
        self,
        account_number: str,
        amount: float,
        external_id: str,
        provider: Optional[Provider] = None,
        recipient_name: Optional[str] = None,
        remarks: Optional[str] = None,
    ) -> Disbursement:
        """Send a payout from your gateway balance to a mobile money account."""
        resolved_provider = _resolve_provider(account_number, provider)
        payload = {
            "account_number": account_number,
            "amount": amount,
            "provider": resolved_provider,
            "external_id": external_id,
        }
        if recipient_name:
            payload["recipient_name"] = recipient_name
        if remarks:
            payload["remarks"] = remarks

        response = await self._client.post("/disbursements", json=payload)
        data = await self._handle_response(response)
        return Disbursement.from_dict(data)

    async def get_disbursement_status(self, reference: str) -> Disbursement:
        """Check the status of a disbursement."""
        response = await self._client.get(f"/disbursements/{reference}/status")
        data = await self._handle_response(response)
        return Disbursement.from_dict(data)

    async def is_healthy(self) -> bool:
        """
        Check that the gateway is reachable and the key pair is valid.

        See `Dalipay.is_healthy` for how this works - a side-effect-free
        probe against `GET /collections/{uuid}/status` with a random uuid.

        Returns:
            True if the gateway is reachable and the credentials are valid.
        """
        probe_uuid = str(uuid_lib.uuid4())
        try:
            response = await self._client.get(f"/collections/{probe_uuid}/status")
        except httpx.RequestError:
            return False

        if response.status_code == 401:
            return False
        return response.status_code < 500

    async def close(self) -> None:
        """Close the HTTP client."""
        await self._client.aclose()

    async def __aenter__(self) -> "AsyncDalipay":
        return self

    async def __aexit__(self, *args) -> None:
        await self.close()
