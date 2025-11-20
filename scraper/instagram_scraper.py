import json
from typing import Any, Dict, List, Tuple

from .http_client import HttpClient
from .parsers.profile_parser import ProfileParseError, parse_profile
from .parsers.post_parser import (
    build_doc_id_variables,
    build_query_hash_variables,
    extract_media_connection,
    normalize_post_node,
)
from .settings import ScraperSettings

MAX_GRAPHQL_PAGE_SIZE = 50


class InstagramScraper:
    def __init__(
        self,
        graphql_doc_id: str | None = None,
        graphql_query_hash: str | None = None,
    ) -> None:
        settings = ScraperSettings.from_env()
        self.graphql_doc_id = graphql_doc_id or settings.graphql_doc_id
        self.graphql_query_hash = graphql_query_hash or settings.graphql_query_hash
        self.graphql_lsd = settings.graphql_lsd

        common_headers = settings.common_headers()
        browser_like = {"Sec-Fetch-Site": "same-origin"}

        self.web_client = HttpClient(
            base_url="https://www.instagram.com",
            extra_headers={**common_headers, **browser_like},
        )

        self.api_client = HttpClient(
            base_url="https://i.instagram.com",
            extra_headers={
                **common_headers,
                "x-ig-app-id": settings.x_ig_app_id,
                **browser_like,
            },
        )

        graphql_headers = {
            **common_headers,
            "X-IG-App-ID": settings.x_ig_app_id,
            "X-Requested-With": "XMLHttpRequest",
            "Accept": "*/*",
            "X-ASBD-ID": settings.asbd_id,
            **browser_like,
        }
        if self.graphql_lsd:
            graphql_headers["X-FB-LSD"] = self.graphql_lsd

        self.graphql_client = HttpClient(
            base_url="https://www.instagram.com",
            extra_headers=graphql_headers,
        )

    def load_user_from_api(self, username: str) -> Dict[str, Any]:
        resp = self.api_client.get(
            "/api/v1/users/web_profile_info/",
            params={"username": username},
        )
        data = resp.json()
        return data["data"]["user"]

    def normalize_profile_from_user(self, user: Dict[str, Any]) -> Dict[str, Any]:
        follower_count = user.get("edge_followed_by", {}).get("count")
        following_count = user.get("edge_follow", {}).get("count")
        posts_count = user.get("edge_owner_to_timeline_media", {}).get("count")

        profile_pic_url = (
            user.get("profile_pic_url_hd")
            or user.get("profile_pic_url")
            or None
        )

        category = (
            user.get("category_name")
            or user.get("business_category_name")
            or user.get("category_enum")
        )

        biography = user.get("biography") or user.get("bio")

        return {
            "username": user.get("username"),
            "full_name": user.get("full_name"),
            "biography": biography,
            "follower_count": follower_count,
            "following_count": following_count,
            "posts_count": posts_count,
            "profile_picture_url": profile_pic_url,
            "is_verified": bool(user.get("is_verified")),
            "category": category,
            "external_url": user.get("external_url"),
            "id": user.get("id"),
        }

    def scrape_profile_fallback(
        self,
        username: str,
    ) -> Tuple[Dict[str, Any], Dict[str, Any] | None]:
        path = f"/{username}/"
        resp = self.web_client.get(path)
        html = resp.text
        profile = parse_profile(html, username=username)
        return profile, None

    def scrape_profile(
        self,
        username: str,
    ) -> Tuple[Dict[str, Any], Dict[str, Any] | None]:
        try:
            user = self.load_user_from_api(username)
            profile = self.normalize_profile_from_user(user)
            return profile, user
        except Exception:
            try:
                return self.scrape_profile_fallback(username)
            except ProfileParseError as exc:
                return (
                    {
                        "username": username,
                        "error": f"Unable to parse profile: {exc}",
                    },
                    None,
                )

    def fetch_posts_page(
        self,
        username: str,
        user_id: str,
        after: str | None,
        batch_size: int,
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        tokens: List[Tuple[str, str, Dict[str, Any], bool]] = []
        doc_id_ready = self.graphql_doc_id and self.graphql_lsd

        if doc_id_ready:
            tokens.append(
                (
                    "doc_id",
                    self.graphql_doc_id,
                    build_doc_id_variables(username, after, batch_size),
                    True,
                )
            )
        if self.graphql_query_hash and user_id:
            tokens.append(
                (
                    "query_hash",
                    self.graphql_query_hash,
                    build_query_hash_variables(user_id, after, batch_size),
                    False,
                )
            )

        if not tokens:
            raise RuntimeError(
                "GraphQL pagination requires doc_id or query_hash to be configured."
            )

        last_error: Exception | None = None

        for idx, (token_label, token_value, variables, prefer_xdt) in enumerate(tokens):
            fallback_available = idx < len(tokens) - 1
            serialized_variables = json.dumps(variables, separators=(",", ":"))

            try:
                if token_label == "doc_id":
                    data = {
                        "lsd": self.graphql_lsd,
                        "doc_id": token_value,
                        "variables": serialized_variables,
                    }
                    headers = {
                        "Content-Type": "application/x-www-form-urlencoded",
                        "X-FB-LSD": self.graphql_lsd or "",
                    }
                    resp = self.graphql_client.post(
                        "/graphql/query/",
                        data=data,
                        headers=headers,
                    )
                else:
                    params = {
                        "variables": serialized_variables,
                        token_label: token_value,
                    }
                    resp = self.graphql_client.get(
                        "/graphql/query/",
                        params=params,
                    )
            except Exception as exc:
                last_error = exc
                if fallback_available:
                    continue
                raise

            try:
                data = resp.json()
            except Exception as exc:
                last_error = RuntimeError("Failed to decode GraphQL JSON")
                if fallback_available:
                    continue
                raise last_error from exc

            errors = data.get("errors")
            if errors:
                last_error = RuntimeError(
                    f"Instagram GraphQL returned errors ({token_label}={token_value})"
                )
                if fallback_available:
                    continue
                raise last_error

            media = extract_media_connection(data, prefer_xdt=prefer_xdt)
            if not media:
                last_error = RuntimeError(
                    f"Unexpected GraphQL payload shape ({token_label}={token_value})"
                )
                if fallback_available:
                    continue
                raise last_error

            edges = media.get("edges", [])
            normalized = [
                normalize_post_node(edge.get("node", {}))
                for edge in edges
            ]

            page_info = media.get("page_info", {}) or {}
            return normalized, page_info

        if last_error:
            raise last_error
        raise RuntimeError("Unable to fetch posts page via GraphQL")

    def scrape_posts(
        self,
        username: str,
        min_count: int = 50,
        user_data: Dict[str, Any] | None = None,
    ) -> List[Dict[str, Any]]:
        if min_count <= 0:
            return []

        if user_data is None:
            try:
                user_data = self.load_user_from_api(username)
            except Exception:
                return []

        timeline = user_data.get("edge_owner_to_timeline_media") or {}
        edges = timeline.get("edges") or []

        posts = [
            normalize_post_node(edge.get("node", {})) for edge in edges
        ]

        page_info = timeline.get("page_info") or {}
        has_next = page_info.get("has_next_page", False)
        after = page_info.get("end_cursor")
        user_id = user_data.get("id")

        while has_next and user_id and len(posts) < min_count:
            batch_size = min(MAX_GRAPHQL_PAGE_SIZE, max(1, min_count - len(posts)))

            try:
                page_posts, page_info = self.fetch_posts_page(
                    username=username,
                    user_id=user_id,
                    after=after,
                    batch_size=batch_size,
                )
            except Exception:
                break

            posts.extend(page_posts)
            has_next = page_info.get("has_next_page", False)
            after = page_info.get("end_cursor")

        return posts[:min_count]

    def scrape(self, username: str, min_posts: int = 50) -> Dict[str, Any]:
        profile, user_data = self.scrape_profile(username)
        posts = self.scrape_posts(username, min_posts, user_data=user_data)
        return {
            "profile": profile,
            "posts": posts,
        }
