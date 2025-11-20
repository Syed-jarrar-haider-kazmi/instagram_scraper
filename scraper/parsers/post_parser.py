from typing import Any, Dict, List, Tuple

MEDIA_TYPE_MAP = {
    "GraphImage": "image",
    "GraphVideo": "video",
    "GraphSidecar": "carousel",
    "GraphClip": "reel",
    "GraphStoryImage": "image",
    "GraphStoryVideo": "video",
    "XDTMediaDict": None,
    "MEDIA_TYPE_IMAGE": "image",
    "MEDIA_TYPE_VIDEO": "video",
    "MEDIA_TYPE_CAROUSEL": "carousel",
    "MEDIA_TYPE_REEL": "reel",
    "clips": "reel",
    "clip": "reel",
    "carousel_container": "carousel",
    "feed": None,
}
NUMERIC_MEDIA_MAP = {
    1: "image",
    2: "video",
    8: "carousel",
}


def extract_caption(node: Dict[str, Any]) -> str | None:
    caption_obj = node.get("caption")
    if isinstance(caption_obj, dict):
        text = caption_obj.get("text")
        if text:
            return text
    elif isinstance(caption_obj, str) and caption_obj:
        return caption_obj

    edges = (node.get("edge_media_to_caption") or {}).get("edges", [])
    if edges:
        return edges[0].get("node", {}).get("text")
    return None


def _extend_from_versions(media: Dict[str, Any], urls: List[str]) -> None:
    img = media.get("image_versions2") or {}
    for cand in img.get("candidates", []):
        url = cand.get("url")
        if url:
            urls.append(url)

    for video in media.get("video_versions") or []:
        url = video.get("url")
        if url:
            urls.append(url)


def extract_media_urls(node: Dict[str, Any]) -> List[str]:
    urls: List[str] = []

    carousel = node.get("carousel_media")
    if isinstance(carousel, list) and carousel:
        for item in carousel:
            if isinstance(item, dict):
                _extend_from_versions(item, urls)
        if urls:
            return urls

    _extend_from_versions(node, urls)
    if urls:
        return urls

    typename = node.get("__typename") or node.get("media_type")
    if typename == "GraphSidecar" and node.get("edge_sidecar_to_children"):
        for child in node["edge_sidecar_to_children"].get("edges", []):
            child_node = child.get("node", {})
            media_url = child_node.get("video_url") or child_node.get("display_url")
            if media_url:
                urls.append(media_url)
    else:
        media_url = node.get("video_url") or node.get("display_url")
        if media_url:
            urls.append(media_url)

    return urls


def map_media_type(raw_type: Any) -> str | None:
    typename = raw_type
    if isinstance(typename, str):
        if typename.isdigit():
            typename = int(typename)
        else:
            lowered = typename.lower()
            mapped = MEDIA_TYPE_MAP.get(lowered)
            if mapped is not None:
                return mapped
            mapped = MEDIA_TYPE_MAP.get(typename)
            if mapped:
                return mapped
    if isinstance(typename, (int, float)):
        return NUMERIC_MEDIA_MAP.get(int(typename))
    return MEDIA_TYPE_MAP.get(typename)


def normalize_post_node(node: Dict[str, Any]) -> Dict[str, Any]:
    typename = (
        node.get("__typename")
        or node.get("media_type")
        or node.get("product_type")
        or "XDTMediaDict"
    )
    shortcode = node.get("shortcode") or node.get("code")
    location = node.get("location")
    loc_id = loc_name = None
    if isinstance(location, dict):
        loc_id = location.get("pk") or location.get("id")
        loc_name = location.get("name")

    return {
        "id": node.get("id") or node.get("pk"),
        "shortcode": shortcode,
        "caption": extract_caption(node),
        "like_count": node.get("like_count")
        or node.get("edge_liked_by", {}).get("count")
        or node.get("edge_media_preview_like", {}).get("count"),
        "comment_count": node.get("comment_count")
        or node.get("edge_media_to_comment", {}).get("count"),
        "timestamp": node.get("taken_at") or node.get("taken_at_timestamp"),
        "media_type": map_media_type(typename) or typename,
        "media_urls": extract_media_urls(node),
        "location": (
            {"id": loc_id, "name": loc_name} if (loc_id or loc_name) else None
        ),
        "permalink": f"https://www.instagram.com/p/{shortcode}/" if shortcode else None,
        "view_count": node.get("view_count")
        or node.get("video_view_count")
        or node.get("play_count"),
    }


def build_doc_id_variables(
    username: str,
    after: str | None,
    batch_size: int,
) -> Dict[str, Any]:
    return {
        "after": after,
        "before": None,
        "data": {
            "count": batch_size,
            "include_reel_media_seen_timestamp": True,
            "include_relationship_info": True,
            "latest_besties_reel_media": True,
            "latest_reel_media": True,
        },
        "first": batch_size,
        "last": None,
        "username": username,
        "__relay_internal__pv__PolarisIsLoggedInrelayprovider": True,
    }


def build_query_hash_variables(
    user_id: str,
    after: str | None,
    batch_size: int,
) -> Dict[str, Any]:
    return {
        "id": user_id,
        "first": batch_size,
        "after": after,
    }


def extract_media_connection(
    payload: Dict[str, Any],
    prefer_xdt: bool,
) -> Dict[str, Any] | None:
    data_root = payload.get("data") or {}

    def from_path(path: List[str]) -> Dict[str, Any] | None:
        cursor: Any = data_root
        for part in path:
            if not isinstance(cursor, dict):
                return None
            cursor = cursor.get(part)
        return cursor if isinstance(cursor, dict) else None

    xdt_keys = [
        "xdt_api__v1__feed__user_timeline_graphql_connection",
        "xdt_api_v1_feed_user_timeline_graphql_connection",
    ]
    legacy_path = ["user", "edge_owner_to_timeline_media"]

    path_candidates: List[List[str]] = []
    xdt_paths = [[key] for key in xdt_keys]
    if prefer_xdt:
        path_candidates.extend(xdt_paths)
        path_candidates.append(legacy_path)
    else:
        path_candidates.append(legacy_path)
        path_candidates.extend(xdt_paths)

    for path in path_candidates:
        timeline = from_path(path)
        if timeline:
            return timeline

    for key, value in data_root.items():
        if (
            isinstance(value, dict)
            and "edges" in value
            and "page_info" in value
            and "timeline" in key
        ):
            return value

    return None
