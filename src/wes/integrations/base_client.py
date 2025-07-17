"""Base client for all integration services with common functionality."""

import asyncio
import time
from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

import aiohttp

from ..utils.exceptions import (
    AuthenticationError,
    ConnectionError,
    IntegrationError,
    RateLimitError,
)
from ..utils.logging_config import get_logger, get_security_logger


class RateLimiter:
    """Rate limiter for API requests with backoff strategy."""

    def __init__(self, max_requests: int = 100, time_window: int = 60):
        self.max_requests = max_requests
        self.time_window = time_window
        self.requests = []
        self._lock = asyncio.Lock()
        self.logger = get_logger(__name__)

    async def acquire(self) -> None:
        """Acquire rate limit permit with exponential backoff."""
        async with self._lock:
            now = time.time()

            # Remove old requests outside the time window
            self.requests = [
                req_time
                for req_time in self.requests
                if now - req_time < self.time_window
            ]

            # Check if we're at the limit
            if len(self.requests) >= self.max_requests:
                wait_time = self.time_window - (now - self.requests[0])
                if wait_time > 0:
                    self.logger.warning(
                        f"Rate limit reached, waiting {wait_time:.2f} seconds"
                    )
                    await asyncio.sleep(wait_time)
                    return await self.acquire()

            # Add current request
            self.requests.append(now)

    def reset(self) -> None:
        """Reset rate limiter state."""
        self.requests.clear()

    @property
    def current_usage(self) -> float:
        """Get current usage percentage."""
        now = time.time()
        active_requests = [req for req in self.requests if now - req < self.time_window]
        return (len(active_requests) / self.max_requests) * 100


class RetryStrategy:
    """Retry strategy with exponential backoff."""

    def __init__(
        self,
        max_retries: int = 3,
        initial_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0,
        jitter: bool = True,
    ):
        self.max_retries = max_retries
        self.initial_delay = initial_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter

    def get_delay(self, retry_count: int) -> float:
        """Calculate delay for the given retry count."""
        delay = min(
            self.initial_delay * (self.exponential_base**retry_count),
            self.max_delay,
        )

        if self.jitter:
            # Add random jitter to prevent thundering herd
            import random

            delay = delay * (0.5 + random.random() * 0.5)

        return delay

    async def execute_with_retry(
        self,
        func: Callable,
        *args,
        retry_on: Optional[List[type]] = None,
        **kwargs,
    ) -> Any:
        """Execute function with retry logic."""
        retry_on = retry_on or [ConnectionError, RateLimitError]
        last_exception = None

        for attempt in range(self.max_retries + 1):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                last_exception = e

                # Check if we should retry this exception
                should_retry = any(isinstance(e, exc_type) for exc_type in retry_on)

                if not should_retry or attempt == self.max_retries:
                    raise

                # Calculate and apply delay
                delay = self.get_delay(attempt)
                await asyncio.sleep(delay)

        raise last_exception


class BaseIntegrationClient(ABC):
    """Base class for all integration clients."""

    def __init__(
        self,
        base_url: str,
        rate_limit: int = 100,
        timeout: int = 30,
        max_retries: int = 3,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.logger = get_logger(self.__class__.__name__)
        self.security_logger = get_security_logger()

        # Rate limiting
        self.rate_limiter = RateLimiter(max_requests=rate_limit, time_window=60)

        # Retry strategy
        self.retry_strategy = RetryStrategy(max_retries=max_retries)

        # Connection pool
        self._session: Optional[aiohttp.ClientSession] = None
        self._session_lock = asyncio.Lock()

        # Metrics
        self.metrics = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "total_latency": 0.0,
            "last_request_time": None,
        }

    @abstractmethod
    async def authenticate(self) -> bool:
        """Authenticate with the service."""

    @abstractmethod
    async def validate_connection(self) -> bool:
        """Validate the connection to the service."""

    @asynccontextmanager
    async def get_session(self):
        """Get or create aiohttp session with connection pooling."""
        async with self._session_lock:
            if self._session is None or self._session.closed:
                connector = aiohttp.TCPConnector(
                    limit=50,  # Total connection pool size
                    limit_per_host=10,  # Per-host connection limit
                    ttl_dns_cache=300,  # DNS cache timeout
                )
                timeout_config = aiohttp.ClientTimeout(total=self.timeout)

                self._session = aiohttp.ClientSession(
                    connector=connector,
                    timeout=timeout_config,
                    headers=self._get_default_headers(),
                )

            yield self._session

    def _get_default_headers(self) -> Dict[str, str]:
        """Get default headers for requests."""
        return {
            "User-Agent": "WES-ExecutiveSummaryTool/1.0",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    async def _make_request(
        self,
        method: str,
        endpoint: str,
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
        retry_on: Optional[List[type]] = None,
    ) -> Dict[str, Any]:
        """Make HTTP request with rate limiting and retry logic."""
        # Rate limiting
        await self.rate_limiter.acquire()

        # Prepare request
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        request_headers = self._get_default_headers()
        if headers:
            request_headers.update(headers)

        # Log request (sanitized)
        self.logger.debug(
            f"Making {method} request to {endpoint}",
            extra={"params": params, "has_body": json_data is not None},
        )

        # Track metrics
        start_time = time.time()
        self.metrics["total_requests"] += 1

        async def _execute_request():
            async with self.get_session() as session:
                async with session.request(
                    method=method,
                    url=url,
                    headers=request_headers,
                    params=params,
                    json=json_data,
                ) as response:
                    # Handle rate limiting
                    if response.status == 429:
                        retry_after = response.headers.get("Retry-After", "60")
                        raise RateLimitError(
                            f"Rate limit exceeded. Retry after {retry_after} seconds"
                        )

                    # Handle authentication errors
                    if response.status in [401, 403]:
                        raise AuthenticationError(
                            f"Authentication failed: {response.status}"
                        )

                    # Handle other errors
                    if response.status >= 400:
                        error_text = await response.text()
                        raise IntegrationError(
                            f"Request failed with status "
                            f"{response.status}: {error_text}"
                        )

                    # Parse response
                    if response.content_type == "application/json":
                        return await response.json()
                    else:
                        return {"content": await response.text()}

        try:
            # Execute with retry
            result = await self.retry_strategy.execute_with_retry(
                _execute_request, retry_on=retry_on
            )

            # Update metrics
            self.metrics["successful_requests"] += 1
            self.metrics["total_latency"] += time.time() - start_time
            self.metrics["last_request_time"] = datetime.now()

            return result

        except Exception as e:
            # Update metrics
            self.metrics["failed_requests"] += 1

            # Log error
            self.logger.error(
                f"Request failed: {method} {endpoint}",
                exc_info=True,
                extra={"error": str(e)},
            )

            raise

    async def get(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Make GET request."""
        return await self._make_request("GET", endpoint, headers=headers, params=params)

    async def post(
        self,
        endpoint: str,
        json_data: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Make POST request."""
        return await self._make_request(
            "POST", endpoint, headers=headers, json_data=json_data
        )

    async def put(
        self,
        endpoint: str,
        json_data: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Make PUT request."""
        return await self._make_request(
            "PUT", endpoint, headers=headers, json_data=json_data
        )

    async def delete(
        self, endpoint: str, headers: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """Make DELETE request."""
        return await self._make_request("DELETE", endpoint, headers=headers)

    async def close(self):
        """Close the client and cleanup resources."""
        if self._session and not self._session.closed:
            await self._session.close()

        self.logger.info(
            "Client closed",
            extra={
                "metrics": self.metrics,
                "rate_limit_usage": f"{self.rate_limiter.current_usage:.1f}%",
            },
        )

    def get_metrics(self) -> Dict[str, Any]:
        """Get client metrics."""
        metrics = self.metrics.copy()

        # Calculate average latency
        if metrics["successful_requests"] > 0:
            metrics["average_latency"] = (
                metrics["total_latency"] / metrics["successful_requests"]
            )
        else:
            metrics["average_latency"] = 0.0

        # Add rate limiter info
        metrics["rate_limit_usage"] = f"{self.rate_limiter.current_usage:.1f}%"

        return metrics

    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on the service."""
        try:
            # Validate connection
            is_healthy = await self.validate_connection()

            return {
                "healthy": is_healthy,
                "service": self.__class__.__name__,
                "metrics": self.get_metrics(),
                "timestamp": datetime.now().isoformat(),
            }

        except Exception as e:
            return {
                "healthy": False,
                "service": self.__class__.__name__,
                "error": str(e),
                "metrics": self.get_metrics(),
                "timestamp": datetime.now().isoformat(),
            }

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        _ = exc_type, exc_val, exc_tb  # Unused but required by protocol
        asyncio.create_task(self.close())

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        _ = exc_type, exc_val, exc_tb  # Unused but required by protocol
        await self.close()
