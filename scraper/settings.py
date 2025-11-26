import os
from dataclasses import dataclass
from typing import Dict, Optional


@dataclass(frozen=True)
class ScraperSettings:
    cookie: str
    x_ig_app_id: str
    asbd_id: str
    graphql_lsd: Optional[str]
    graphql_doc_id: str
    graphql_query_hash: str

    @classmethod
    def from_env(cls) -> "ScraperSettings":
        return cls(
            cookie=os.getenv("COOKIE", ""),
            x_ig_app_id=os.getenv("X_IG_APP_ID"),
            asbd_id=os.getenv("IG_ASBD_ID", "129477"),
            graphql_lsd=os.getenv("IG_LSD"),
            graphql_doc_id=os.getenv("IG_GRAPHQL_DOC_ID", "32820268350897851"),
            graphql_query_hash=os.getenv(
                "IG_GRAPHQL_QUERY_HASH", "8c2a529969ee035a5063f2fc8602a0fd"
            ),
        )

    def common_headers(self) -> Dict[str, str]:
        headers: Dict[str, str] = {}
        if self.cookie:
            headers["Cookie"] = self.cookie
            for part in self.cookie.split(";"):
                part = part.strip()
                if part.lower().startswith("csrftoken="):
                    headers["X-CSRFToken"] = part.split("=", 1)[1]
                    break
        return headers
