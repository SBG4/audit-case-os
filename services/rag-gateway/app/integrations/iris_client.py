"""
IRIS API Client for case management integration.

Provides async methods to:
- Fetch case metadata
- List case evidence
- Download evidence files

Uses httpx for async HTTP requests with retry logic.
"""

import logging
from typing import Dict, List, Optional, Any
from io import BytesIO

import httpx
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

logger = logging.getLogger(__name__)


class IrisAPIError(Exception):
    """Base exception for IRIS API errors."""
    pass


class IrisNotFoundError(IrisAPIError):
    """Raised when a resource is not found (404)."""
    pass


class IrisAuthenticationError(IrisAPIError):
    """Raised when authentication fails (401)."""
    pass


class IrisClient:
    """
    Async client for IRIS (DFIR-IRIS) API.

    Handles authentication, retries, and error handling for all IRIS operations.
    """

    def __init__(
        self,
        base_url: str,
        api_key: str,
        timeout: float = 30.0,
        max_retries: int = 3,
    ):
        """
        Initialize IRIS API client.

        Args:
            base_url: IRIS API base URL (e.g., "http://iris-app:8000")
            api_key: IRIS API key for authentication
            timeout: Request timeout in seconds
            max_retries: Maximum number of retry attempts
        """
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self.max_retries = max_retries

        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            timeout=httpx.Timeout(timeout),
            follow_redirects=True,
        )

        logger.info(f"Initialized IRIS client for {self.base_url}")

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.NetworkError, httpx.TimeoutException)),
    )
    async def _request(
        self,
        method: str,
        path: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Make an authenticated request to IRIS API with retry logic.

        Args:
            method: HTTP method (GET, POST, etc.)
            path: API path (e.g., "/manage/cases/1")
            **kwargs: Additional arguments passed to httpx.request()

        Returns:
            JSON response as dictionary

        Raises:
            IrisAuthenticationError: If authentication fails
            IrisNotFoundError: If resource not found
            IrisAPIError: For other API errors
        """
        try:
            response = await self.client.request(method, path, **kwargs)

            # Handle specific HTTP status codes
            if response.status_code == 401:
                raise IrisAuthenticationError("Invalid or expired API key")
            elif response.status_code == 404:
                raise IrisNotFoundError(f"Resource not found: {path}")
            elif response.status_code >= 400:
                error_detail = response.text
                raise IrisAPIError(
                    f"IRIS API error {response.status_code}: {error_detail}"
                )

            response.raise_for_status()

            # Parse JSON response
            try:
                data = response.json()
                return data
            except ValueError as e:
                logger.error(f"Failed to parse JSON response: {e}")
                raise IrisAPIError(f"Invalid JSON response from IRIS: {e}")

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error {e.response.status_code}: {e}")
            raise IrisAPIError(f"HTTP error: {e}")
        except httpx.NetworkError as e:
            logger.warning(f"Network error, will retry: {e}")
            raise  # Let tenacity retry
        except httpx.TimeoutException as e:
            logger.warning(f"Request timeout, will retry: {e}")
            raise  # Let tenacity retry

    async def get_case(self, case_id: int) -> Dict[str, Any]:
        """
        Fetch case metadata from IRIS.

        Args:
            case_id: IRIS case ID

        Returns:
            Case metadata dictionary with keys:
            - case_id, case_name, case_description
            - client_name, case_open_date, case_close_date
            - owner, opened_by, etc.

        Raises:
            IrisNotFoundError: If case doesn't exist
            IrisAPIError: For other API errors
        """
        logger.info(f"Fetching case {case_id} from IRIS")

        # Try to get case details from the cases list endpoint
        response = await self._request("GET", "/manage/cases/list")

        # IRIS returns: {"status": "success", "data": [...]}
        if response.get("status") != "success":
            raise IrisAPIError(f"Unexpected response status: {response.get('status')}")

        cases = response.get("data", [])

        # Find the case by ID
        case = next((c for c in cases if c.get("case_id") == case_id), None)

        if not case:
            raise IrisNotFoundError(f"Case {case_id} not found")

        logger.info(f"Successfully fetched case: {case.get('case_name')}")
        return case

    async def list_case_evidence(self, case_id: int) -> List[Dict[str, Any]]:
        """
        List all evidence files for a case.

        Args:
            case_id: IRIS case ID

        Returns:
            List of evidence dictionaries with keys:
            - id (evidence ID)
            - filename
            - file_size
            - file_description
            - custom_attributes

        Raises:
            IrisNotFoundError: If case doesn't exist
            IrisAPIError: For other API errors
        """
        logger.info(f"Listing evidence for case {case_id}")

        # IRIS endpoint: /case/evidences/list?cid={case_id}
        response = await self._request(
            "GET",
            "/case/evidences/list",
            params={"cid": case_id},
        )

        # IRIS returns: {"status": "success", "data": {"evidences": [...]}}
        if response.get("status") != "success":
            raise IrisAPIError(f"Unexpected response status: {response.get('status')}")

        data = response.get("data", {})
        evidences = data.get("evidences", [])

        logger.info(f"Found {len(evidences)} evidence files for case {case_id}")
        return evidences

    async def download_evidence(
        self,
        evidence_id: int,
        case_id: int,
    ) -> bytes:
        """
        Download evidence file content.

        Args:
            evidence_id: IRIS evidence ID
            case_id: IRIS case ID

        Returns:
            File content as bytes

        Raises:
            IrisNotFoundError: If evidence doesn't exist
            IrisAPIError: For other API errors
        """
        logger.info(f"Downloading evidence {evidence_id} from case {case_id}")

        # IRIS endpoint: /case/evidences/{evidence_id}/download?cid={case_id}
        path = f"/case/evidences/{evidence_id}/download"

        try:
            response = await self.client.get(
                path,
                params={"cid": case_id},
                timeout=httpx.Timeout(300.0),  # 5 min for large files
            )

            if response.status_code == 404:
                raise IrisNotFoundError(f"Evidence {evidence_id} not found")
            elif response.status_code >= 400:
                raise IrisAPIError(
                    f"Failed to download evidence: HTTP {response.status_code}"
                )

            response.raise_for_status()

            content = response.content
            logger.info(
                f"Successfully downloaded evidence {evidence_id} ({len(content)} bytes)"
            )
            return content

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error downloading evidence: {e}")
            raise IrisAPIError(f"Failed to download evidence: {e}")
        except httpx.NetworkError as e:
            logger.error(f"Network error downloading evidence: {e}")
            raise IrisAPIError(f"Network error: {e}")
        except httpx.TimeoutException as e:
            logger.error(f"Timeout downloading evidence: {e}")
            raise IrisAPIError(f"Download timeout: {e}")

    async def health_check(self) -> bool:
        """
        Check if IRIS API is accessible.

        Returns:
            True if IRIS is healthy, False otherwise
        """
        try:
            response = await self._request("GET", "/api/versions")
            return response.get("status") == "success"
        except Exception as e:
            logger.error(f"IRIS health check failed: {e}")
            return False
