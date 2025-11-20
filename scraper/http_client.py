import random
import time
from typing import Optional, Dict, Any

import requests

DEFAULT_TIMEOUT = 15

USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
]


class HttpClient:
    def __init__(
        self,
        base_url: str = "https://www.instagram.com",
        extra_headers: Optional[Dict[str, str]] = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.extra_headers = extra_headers or {}

    def _random_headers(self) -> Dict[str, str]:
        headers: Dict[str, str] = {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://www.instagram.com/",
        }
        headers.update(self.extra_headers)
        return headers

    def get(
        self,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        max_retries: int = 3,
        timeout: int = DEFAULT_TIMEOUT,
        headers: Optional[Dict[str, str]] = None,
    ) -> requests.Response:
        """Basic GET with simple exponential backoff."""
        url = path if path.startswith("http") else f"{self.base_url}{path}"

        attempt = 0
        last_exc: Optional[Exception] = None

        while attempt <= max_retries:
            try:
                request_headers = self._random_headers()
                if headers:
                    request_headers.update(headers)
                resp = self.session.get(
                    url,
                    params=params,
                    headers=request_headers,
                    timeout=timeout,
                )

                if resp.status_code in (429, 500, 502, 503, 504):
                    sleep_for = 2 ** attempt
                    time.sleep(sleep_for)
                    attempt += 1
                    continue

                resp.raise_for_status()
                return resp
            except requests.RequestException as exc:
                last_exc = exc
                sleep_for = 2 ** attempt
                time.sleep(sleep_for)
                attempt += 1

        raise RuntimeError(f"GET {url} failed after retries") from last_exc

    def post(
        self,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
        json: Optional[Any] = None,
        max_retries: int = 3,
        timeout: int = DEFAULT_TIMEOUT,
        headers: Optional[Dict[str, str]] = None,
    ) -> requests.Response:
        """POST helper mirroring the retry logic from GET."""
        url = path if path.startswith("http") else f"{self.base_url}{path}"

        attempt = 0
        last_exc: Optional[Exception] = None

        while attempt <= max_retries:
            try:
                request_headers = self._random_headers()
                if headers:
                    request_headers.update(headers)
                resp = self.session.post(
                    url,
                    params=params,
                    data=data,
                    json=json,
                    headers=request_headers,
                    timeout=timeout,
                )

                if resp.status_code in (429, 500, 502, 503, 504):
                    sleep_for = 2 ** attempt
                    time.sleep(sleep_for)
                    attempt += 1
                    continue

                resp.raise_for_status()
                return resp
            except requests.RequestException as exc:
                last_exc = exc
                sleep_for = 2 ** attempt
                time.sleep(sleep_for)
                attempt += 1

        raise RuntimeError(f"POST {url} failed after retries") from last_exc
