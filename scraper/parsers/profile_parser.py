import json
from typing import Any, Dict
from bs4 import BeautifulSoup

class ProfileParseError(Exception):
    pass

def extract_json_from_script_tag(script_text: str) -> Dict[str, Any]:
    if not script_text:
        raise ProfileParseError("Empty script tag")

    start = script_text.find("{")
    end = script_text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ProfileParseError("Could not locate JSON braces in script")

    raw_json = script_text[start : end + 1]

    try:
        return json.loads(raw_json)
    except json.JSONDecodeError as exc:
        raise ProfileParseError("Failed to parse JSON from script") from exc


def extract_user_object(data: Dict[str, Any]) -> Dict[str, Any]:
    try:
        return data["entry_data"]["ProfilePage"][0]["graphql"]["user"]
    except Exception:
        pass

    for path in [
        ("graphql", "user"),
        ("data", "user"),
    ]:
        cur: Any = data
        try:
            for key in path:
                cur = cur[key]
            if isinstance(cur, dict) and cur.get("username"):
                return cur
        except Exception:
            continue

    raise ProfileParseError("Could not locate user object in JSON")


def parse_profile(html: str, username: str) -> Dict[str, Any]:
    soup = BeautifulSoup(html, "lxml")

    json_data: Dict[str, Any] | None = None

    for script in soup.find_all("script"):
        text = script.string or script.text
        if not text:
            continue

        if (
            "ProfilePage" in text
            or "graphql" in text
            or "edge_followed_by" in text
            or "profile_pic_url" in text
        ):
            try:
                json_data = extract_json_from_script_tag(text)
                break
            except ProfileParseError:
                continue

    if json_data is None:
        raise ProfileParseError("Could not find embedded JSON for profile")

    user = extract_user_object(json_data)

    follower_count = None
    following_count = None
    posts_count = None

    try:
        follower_count = user.get("edge_followed_by", {}).get("count")
    except Exception:
        pass

    try:
        following_count = user.get("edge_follow", {}).get("count")
    except Exception:
        pass

    try:
        posts_count = user.get("edge_owner_to_timeline_media", {}).get("count")
    except Exception:
        posts_count = posts_count or user.get("media", {}).get("count")

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

    normalized = {
        "username": user.get("username") or username,
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

    return normalized
