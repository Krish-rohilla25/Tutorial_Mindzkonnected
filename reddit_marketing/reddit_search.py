"""
Reddit search using Tavily (include_domains=["reddit.com"]) and RSS feeds.
"""

import os
import re
import xml.etree.ElementTree as ET
from urllib.request import urlopen, Request
from urllib.parse import quote_plus, urlencode, urlparse, urlunparse
from html import unescape
from datetime import datetime, timezone

from langchain_tavily import TavilySearch


USER_AGENT = "MindzKonnectedRedditMarketing/1.0"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _clean_subreddit(url_or_name: str) -> str:
    """Normalize subreddit — extract from URL or strip r/ prefix."""
    match = re.search(r"reddit\.com/r/([^/?\s]+)", url_or_name)
    if match:
        return match.group(1)
    s = url_or_name.strip()
    while s.startswith("r/"):
        s = s[2:]
    return s


def _extract_subreddit(url: str) -> str:
    """Pull the subreddit name from a Reddit URL."""
    match = re.search(r"reddit\.com/r/([^/?\s]+)", url)
    return match.group(1) if match else "unknown"


def _request_text(url: str, timeout: int = 10) -> str:
    """Fetch URL text with a Reddit-friendly user agent."""
    req = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8")


def _request_json(url: str, timeout: int = 10):
    """Fetch JSON from Reddit without requiring API credentials."""
    import json

    return json.loads(_request_text(url, timeout=timeout))


def _reddit_json_url(url: str) -> str:
    """Convert a reddit.com URL into its .json endpoint."""
    clean = url.split("#")[0]
    parsed = urlparse(clean)
    path = parsed.path.rstrip("/")
    if not path.endswith(".json"):
        path = f"{path}.json"
    return urlunparse((parsed.scheme or "https", parsed.netloc or "www.reddit.com", path, "", parsed.query, ""))


def _reddit_rss_url(url: str, sort: str = None, limit: int = None) -> str:
    """Convert a reddit.com URL into its .rss endpoint."""
    clean = url.split("#")[0].split("?")[0] 
    parsed = urlparse(clean)
    path = parsed.path.rstrip("/")
    if not path.endswith(".rss"):
        path = f"{path}.rss"
    query_parts = []
    if sort:
        query_parts.append(f"sort={sort}")
    if limit:
        # Add 1 to limit to account for the post itself which is returned as the first entry
        query_parts.append(f"limit={limit + 1}")
    query = "&".join(query_parts)
    return urlunparse((parsed.scheme or "https", parsed.netloc or "www.reddit.com", path, "", query, ""))


def _html_to_text(html: str, limit: int = None) -> str:
    """Strip Reddit Atom HTML to readable text."""
    text = re.sub(r"<[^>]+>", " ", unescape(html or ""))
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit] if limit else text


def _get_tavily_tool(tavily_api_key: str, max_results: int = 10, time_range: str = None) -> TavilySearch:
    """Create a TavilySearch tool locked to reddit.com."""
    os.environ["TAVILY_API_KEY"] = tavily_api_key
    return TavilySearch(
        max_results=max_results,
        search_depth="advanced",
        include_domains=["reddit.com"],
        time_range=time_range,
    )


# ---------------------------------------------------------------------------
# Tavily-based post/thread search
# ---------------------------------------------------------------------------

def search_reddit(tavily_api_key: str, query: str, max_results: int = 10, time_range: str = None) -> list:
    """
    Search Reddit via Tavily.

    Returns a list of dicts: {title, url, content, subreddit, type, source}
    """
    tool = _get_tavily_tool(tavily_api_key, max_results, time_range)
    result = tool.invoke(query)

    if isinstance(result, dict) and "error" in result:
        raise Exception(f"Tavily API Error: {result['error']}")

    opportunities = []
    for r in result.get("results", []):
        url = r.get("url", "")
        if "reddit.com" not in url:
            continue

        is_thread = "/comments/" in url
        opportunities.append({
            "title": r.get("title", ""),
            "url": url,
            "content": r.get("content", ""),
            "subreddit": _extract_subreddit(url),
            "type": "reply" if is_thread else "post",
            "source": "tavily",
        })

    return opportunities


def search_subreddit(tavily_api_key: str, subreddit: str, query: str, max_results: int = 5) -> list:
    """Search within a specific subreddit."""
    full_query = f"{query} r/{subreddit}"
    return search_reddit(tavily_api_key, full_query, max_results)


# ---------------------------------------------------------------------------
# Direct Reddit JSON search/thread extraction
# ---------------------------------------------------------------------------

def search_reddit_json(query: str, max_results: int = 10, time_range: str = "month", subreddit: str = None) -> list:
    """
    Search Reddit through public JSON endpoints.

    This avoids Tavily for basic discovery. Reddit may rate-limit anonymous
    traffic, so callers should keep Tavily as a fallback for production use.
    """
    params = {
        "q": query,
        "sort": "relevance",
        "limit": max_results,
        "t": time_range or "all",
        "raw_json": 1,
    }

    if subreddit:
        sub = _clean_subreddit(subreddit)
        url = f"https://www.reddit.com/r/{quote_plus(sub)}/search.json?{urlencode({**params, 'restrict_sr': 1})}"
    else:
        url = f"https://www.reddit.com/search.json?{urlencode(params)}"

    try:
        payload = _request_json(url)
    except Exception:
        return []

    opportunities = []
    for child in payload.get("data", {}).get("children", []):
        data = child.get("data", {})
        permalink = data.get("permalink", "")
        post_url = f"https://www.reddit.com{permalink}" if permalink else data.get("url", "")
        sub = data.get("subreddit") or _extract_subreddit(post_url)
        body = data.get("selftext") or data.get("url_overridden_by_dest") or ""

        opportunities.append({
            "title": data.get("title", ""),
            "url": post_url,
            "content": body,
            "subreddit": sub,
            "type": "reply",
            "source": "reddit_json",
            "score": data.get("score", 0),
            "num_comments": data.get("num_comments", 0),
            "created_utc": data.get("created_utc"),
        })

    return opportunities


def fetch_post_context(post_url: str) -> dict:
    """Fetch the Reddit post title/body/subreddit from a post URL."""
    try:
        payload = _request_json(_reddit_json_url(post_url))
    except Exception:
        return {}

    if not isinstance(payload, list) or not payload:
        return {}

    post_children = payload[0].get("data", {}).get("children", [])
    if not post_children:
        return {}

    data = post_children[0].get("data", {})
    permalink = data.get("permalink", "")
    return {
        "title": data.get("title", ""),
        "url": f"https://www.reddit.com{permalink}" if permalink else post_url,
        "content": data.get("selftext", ""),
        "subreddit": data.get("subreddit") or _extract_subreddit(post_url),
        "type": "post",
        "source": "reddit_json",
        "score": data.get("score", 0),
        "num_comments": data.get("num_comments", 0),
        "created_utc": data.get("created_utc"),
    }


def fetch_thread_comments(post_url: str, limit: int = 25, sort: str = "confidence") -> list:
    """
    Fetch top-level and nested comments from a Reddit thread JSON URL.

    Returns normalized dicts ready for monitoring/scoring.
    """
    if "/submit" in post_url:
        return []

    base_url = _reddit_json_url(post_url)
    separator = "&" if "?" in base_url else "?"
    url = f"{base_url}{separator}{urlencode({'sort': sort, 'limit': limit, 'raw_json': 1})}"

    try:
        payload = _request_json(url)
    except Exception:
        return []

    if not isinstance(payload, list) or len(payload) < 2:
        return []

    post = fetch_post_context(post_url)
    comments = []

    def walk(children, depth=0):
        for child in children:
            if child.get("kind") != "t1":
                continue
            data = child.get("data", {})
            body = data.get("body", "")
            author = data.get("author", "")
            if not body or body in {"[deleted]", "[removed]"}:
                continue

            permalink = data.get("permalink", "")
            created_utc = data.get("created_utc")
            comments.append({
                "id": data.get("id", ""),
                "parent_id": data.get("parent_id", ""),
                "author": author,
                "body": body,
                "score": data.get("score", 0),
                "created_utc": created_utc,
                "created_at": datetime.fromtimestamp(created_utc, timezone.utc).isoformat() if created_utc else "",
                "permalink": f"https://www.reddit.com{permalink}" if permalink else post_url,
                "post_url": post.get("url", post_url),
                "post_title": post.get("title", ""),
                "post_body": post.get("content", ""),
                "subreddit": post.get("subreddit") or _extract_subreddit(post_url),
                "depth": depth,
                "type": "comment_reply",
                "source": "reddit_json",
            })

            replies = data.get("replies")
            if isinstance(replies, dict):
                walk(replies.get("data", {}).get("children", []), depth + 1)

    walk(payload[1].get("data", {}).get("children", []))
    return comments[:limit]


# ---------------------------------------------------------------------------
# RSS feed monitoring
# ---------------------------------------------------------------------------

def fetch_subreddit_feed(subreddit: str, sort: str = "new", limit: int = 10) -> list:
    """
    Fetch recent posts from a subreddit's RSS feed.

    subreddit: name without r/ prefix
    sort: 'new', 'hot', or 'top'
    Returns a list of dicts: {title, url, content, subreddit, type, source}
    """
    sub = _clean_subreddit(subreddit)
    feed_url = f"https://www.reddit.com/r/{quote_plus(sub)}/{sort}.rss"

    try:
        xml_data = _request_text(feed_url)
    except Exception:
        return []

    return _parse_rss(xml_data, sub, limit)


def _parse_rss(xml_data: str, subreddit: str, limit: int) -> list:
    """Parse Reddit's Atom RSS XML into post dicts."""
    posts = []
    try:
        root = ET.fromstring(xml_data)
    except ET.ParseError:
        return []

    ns = {"atom": "http://www.w3.org/2005/Atom"}
    entries = root.findall("atom:entry", ns)

    for entry in entries[:limit]:
        title_el = entry.find("atom:title", ns)
        link_el = entry.find("atom:link", ns)
        content_el = entry.find("atom:content", ns)

        title = title_el.text if title_el is not None and title_el.text else ""
        url = link_el.get("href", "") if link_el is not None else ""
        content = ""
        if content_el is not None and content_el.text:
            content = _html_to_text(content_el.text, limit=500)

        posts.append({
            "title": title,
            "url": url,
            "content": content,
            "subreddit": subreddit,
            "type": "post",
            "source": "rss",
        })

    return posts


def fetch_thread_comments_rss(post_url: str, limit: int = 50, sort: str = None) -> list:
    """
    Fetch comments from a Reddit thread RSS feed.

    Reddit thread feeds include the original t3 post followed by t1 comment
    entries. Nested comments are included as separate t1 entries with their
    own permalinks, which are enough to open the exact reply target.
    """
    if "/submit" in post_url:
        return []

    try:
        xml_data = _request_text(_reddit_rss_url(post_url, sort=sort, limit=limit))
    except Exception as e:
        raise RuntimeError(f"Failed to fetch Reddit RSS: {e}")

    try:
        root = ET.fromstring(xml_data)
    except ET.ParseError:
        return []

    ns = {"atom": "http://www.w3.org/2005/Atom"}
    feed_title_el = root.find("atom:title", ns)
    feed_title = feed_title_el.text if feed_title_el is not None and feed_title_el.text else ""
    entries = root.findall("atom:entry", ns)
    comments = []
    post_context = {}

    for entry in entries:
        id_el = entry.find("atom:id", ns)
        entry_id = id_el.text if id_el is not None and id_el.text else ""
        title_el = entry.find("atom:title", ns)
        link_el = entry.find("atom:link", ns)
        content_el = entry.find("atom:content", ns)
        updated_el = entry.find("atom:updated", ns)
        author_el = entry.find("atom:author/atom:name", ns)
        category_el = entry.find("atom:category", ns)

        title = title_el.text if title_el is not None and title_el.text else ""
        link = link_el.get("href", "") if link_el is not None else ""
        content = _html_to_text(content_el.text if content_el is not None else "")
        author = author_el.text if author_el is not None and author_el.text else ""
        updated = updated_el.text if updated_el is not None and updated_el.text else ""
        subreddit = ""
        if category_el is not None:
            subreddit = _clean_subreddit(category_el.get("term") or category_el.get("label") or "")
        if not subreddit:
            subreddit = _extract_subreddit(link or post_url)

        if entry_id.startswith("t3_"):
            post_context = {
                "post_title": title,
                "post_body": content,
                "post_url": link or post_url,
                "subreddit": subreddit,
            }
            continue

        if not entry_id.startswith("t1_") or not content:
            continue

        comment_id = entry_id.replace("t1_", "", 1)
        comments.append({
            "id": comment_id,
            "parent_id": "",
            "author": author,
            "body": content,
            "score": 0,
            "created_at": updated,
            "updated_at": updated,
            "permalink": link,
            "post_url": post_context.get("post_url", post_url),
            "post_title": post_context.get("post_title", feed_title),
            "post_body": post_context.get("post_body", ""),
            "subreddit": subreddit or post_context.get("subreddit", _extract_subreddit(post_url)),
            "depth": None,
            "type": "comment_reply",
            "source": "reddit_rss",
        })

    return comments[:limit]

