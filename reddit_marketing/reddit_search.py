"""
Reddit search using Tavily (include_domains=["reddit.com"]) and RSS feeds.
"""

import os
import re
import xml.etree.ElementTree as ET
from urllib.request import urlopen, Request
from urllib.parse import quote_plus
from html import unescape

from langchain_tavily import TavilySearch


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

    opportunities = []
    for r in result.get("results", []):
        url = r.get("url", "")
        if "reddit.com" not in url:
            continue

        is_thread = "/comments/" in url
        opportunities.append({
            "title": r.get("title", ""),
            "url": url,
            "content": r.get("content", "")[:600],
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
        req = Request(feed_url, headers={"User-Agent": "MindzKonnected/1.0"})
        with urlopen(req, timeout=10) as resp:
            xml_data = resp.read().decode("utf-8")
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
            content = re.sub(r"<[^>]+>", "", unescape(content_el.text))[:500]

        posts.append({
            "title": title,
            "url": url,
            "content": content,
            "subreddit": subreddit,
            "type": "post",
            "source": "rss",
        })

    return posts
