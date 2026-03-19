"""Retry decorators with exponential backoff."""

import structlog
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

import httpx

logger = structlog.get_logger()

# For LLM API calls - retry on network/timeout errors
llm_retry = retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    retry=retry_if_exception_type(
        (httpx.TimeoutException, httpx.ConnectError, ConnectionError, TimeoutError)
    ),
    before_sleep=before_sleep_log(logger, "warning"),
    reraise=True,
)

# For n8n API calls - retry on network errors
n8n_retry = retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=15),
    retry=retry_if_exception_type(
        (httpx.TimeoutException, httpx.ConnectError, ConnectionError)
    ),
    before_sleep=before_sleep_log(logger, "warning"),
    reraise=True,
)
