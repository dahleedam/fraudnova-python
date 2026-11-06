"""Internal HTTP layer: builds requests, decodes the envelope, maps errors, retries 429s."""

import platform
from collections.abc import Mapping
from typing import Any, Optional, Union

import httpx

from fraudnova._version import __version__
from fraudnova.exceptions import (
    ApiError,
    RateLimitError,
    TransportError,
    UnexpectedResponseError,
)
from fraudnova.retry import RetryPolicy, parse_retry_after


class Transport:
    def __init__(
        self,
        api_key: str,
        base_url: str,
        timeout: float,
        retry: Optional[RetryPolicy],
        http_client: Optional[httpx.Client],
    ) -> None:
        self._api_key = api_key
        self.base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._retry = retry
        self._client = http_client
        self.owns_client = http_client is None

    def get(
        self,
        path: str,
        params: Optional[Mapping[str, Union[str, int]]] = None,
        authenticated: bool = True,
    ) -> dict[str, Any]:
        return self._send("GET", self.base_url + path, authenticated, params=params)

    def post(self, path: str, json: Mapping[str, Any]) -> dict[str, Any]:
        return self._send("POST", self.base_url + path, True, json=json)

    def close(self) -> None:
        if self.owns_client and self._client is not None:
            self._client.close()

    def _http(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(timeout=httpx.Timeout(self._timeout, connect=10.0))
        return self._client

    def _headers(self, authenticated: bool) -> dict[str, str]:
        headers = {
            "Accept": "application/json",
            "User-Agent": f"fraudnova-python/{__version__} python/{platform.python_version()}",
        }
        if authenticated:
            headers["Authorization"] = f"Bearer {self._api_key}"
        return headers

    def _send(
        self,
        method: str,
        url: str,
        authenticated: bool,
        params: Optional[Mapping[str, Union[str, int]]] = None,
        json: Optional[Mapping[str, Any]] = None,
    ) -> dict[str, Any]:
        attempt = 1
        while True:
            try:
                response = self._http().request(
                    method, url, params=params, json=json, headers=self._headers(authenticated)
                )
            except (httpx.HTTPError, httpx.InvalidURL, httpx.StreamError) as exc:
                raise TransportError(f"FraudNova request failed: {exc}") from exc

            try:
                return self._decode(response)
            except RateLimitError as error:
                delay = self._retry.delay_for(error, attempt) if self._retry else None
                if self._retry is None or delay is None:
                    raise
                self._retry.sleep(delay)
                attempt += 1

    @staticmethod
    def _decode(response: httpx.Response) -> dict[str, Any]:
        status = response.status_code
        if status < 200 or status >= 300:
            raise ApiError.from_response(
                status, response.text, parse_retry_after(response.headers.get("Retry-After"))
            )
        try:
            decoded: Any = response.json()
        except (ValueError, RecursionError):
            decoded = None
        if not isinstance(decoded, dict) or decoded.get("success") is not True:
            raise UnexpectedResponseError(
                status, "Unexpected response body", decoded if isinstance(decoded, dict) else None
            )
        return decoded
