"""
Discovery Agent

"""

import re
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field


class SearchQueries(BaseModel):
    queries: list[str] = Field(description="List of search queries")


class ScoredOpportunity(BaseModel):
    title: str
    url: str
    subreddit: str = Field(description="Subreddit name only — NO r/ prefix")
    relevance: int
    intent: int
    total_score: int
    reasoning: str
    opportunity_type: str = Field(description='Must be "reply_post"')


class OpportunityList(BaseModel):
    opportunities: list[ScoredOpportunity]


class SubredditOpportunity(BaseModel):
    title: str = Field(description="A short recommendation title for this subreddit")
    url: str = Field(description="Subreddit URL")
    subreddit: str = Field(description="Subreddit name only — NO r/ prefix")
    relevance: int
    intent: int
    total_score: int
    reasoning: str
    opportunity_type: str = Field(description='Must be "new_post"')
    evidence: list[str] = Field(description="2-4 examples from discovered threads that justify posting here")


class SubredditOpportunityList(BaseModel):
    opportunities: list[SubredditOpportunity]


class CommentOpportunity(BaseModel):
    id: str
    title: str
    url: str
    subreddit: str
    relevance: int
    intent: int
    total_score: int
    reasoning: str
    opportunity_type: str = Field(description='Must be "comment_reply"')


class CommentOpportunityList(BaseModel):
    opportunities: list[CommentOpportunity]


DISCOVERY_SYSTEM_PROMPT = """You are a Reddit marketing strategist. Your job is to find the best opportunities to promote a product on Reddit in a helpful, non-spammy way.

You will receive:
1. A project brief describing the product.
2. A list of Reddit posts/threads found via search.

For each item, score it on two dimensions (0-10):
- **relevance**: How related is this post/comment to the product?
- **intent**: Is someone asking for help, recommendations, or solutions that the product could address?

Also provide:
- **reasoning**: A one-sentence explanation of why this is (or isn't) a good opportunity.
- **opportunity_type**: 
  - "reply_post" if we should reply directly to this thread/post

IMPORTANT: The subreddit name in your response must be ONLY the subreddit name with NO r/ prefix.
Example: "studytips" NOT "r/studytips"

Respond by strictly following the requested JSON schema. Each opportunity must have:
- title: original post title
- url: original url
- subreddit: subreddit name only — NO r/ prefix
- relevance: 0-10
- intent: 0-10
- total_score: sum of the above (0-20)
- reasoning: one-sentence explanation
- opportunity_type: "reply_post"

Sort your internal list by total_score descending. Only include opportunities with total_score >= 8."""


SUBREDDIT_DISCOVERY_PROMPT = """You are choosing where a product should create an original Reddit post.

You will receive a project brief and evidence from Reddit threads already discovered by search.
Recommend subreddits where an original post would be useful, welcome, and relevant.

Score each subreddit:
- relevance: how aligned the community is with the product and target audience (0-10)
- intent: whether recent threads show people actively discussing problems the product helps with (0-10)

Rules:
- Prefer subreddits supported by multiple strong evidence items.
- Avoid communities where an original post would feel like pure self-promotion.
- The output opportunity_type must be "new_post".
- The URL should be https://www.reddit.com/r/<subreddit>/
- Subreddit must be name only, no r/ prefix.
- Only include opportunities with total_score >= 10.

Respond by strictly following the requested JSON schema."""


COMMENT_DISCOVERY_PROMPT = """You are monitoring comments on Reddit posts for useful, non-spammy follow-up opportunities.

Score each comment:
- relevance: does the comment ask something or raise a point related to the product? (0-10)
- intent: would a helpful reply from the poster be useful here? (0-10)

Only select comments that deserve an actual human-reviewed reply. Skip low-effort, hostile, already-answered,
or purely congratulatory comments.

Respond by strictly following the requested JSON schema. opportunity_type must be "comment_reply"."""


def _clean_subreddit(sub: str) -> str:
    """Normalize — strip any leading r/ prefix."""
    sub = sub.strip()
    while sub.startswith("r/"):
        sub = sub[2:]
    return sub


def generate_search_queries(llm, brief):
    """
    Use the LLM to generate smart search queries from the project brief.
    Returns a list of query strings.
    """
    messages = [
        SystemMessage(content=(
            "You are a Reddit marketing expert. Given a product brief, generate "
            "6-10 search queries that would find Reddit posts and threads "
            "where this product could be genuinely helpful. Think about:\n"
            "- Problems the product solves (people asking for help)\n"
            "- Questions people commonly ask in the target audience's subreddits\n"
            "- Subreddits where the target audience hangs out\n"
            "- Threads with high engagement about related topics"
        )),
        HumanMessage(content=f"Product Brief:\n\n{brief.to_prompt_str()}"),
    ]

    try:
        structured_llm = llm.with_structured_output(SearchQueries)
        response = structured_llm.invoke(messages)
        return response.queries
    except Exception as e:
        print(f"Error generating queries: {e}")
        return []


def score_opportunities(llm, brief, raw_opportunities):
    """
    Use the LLM to score and rank the raw opportunities.

    raw_opportunities: list of dicts from reddit_search module
    Returns a sorted list of scored opportunity dicts.
    """
    if not raw_opportunities:
        return []

    posts_text = ""
    for i, opp in enumerate(raw_opportunities, 1):
        posts_text += (
            f"\n--- Item {i} ---\n"
            f"Title: {opp.get('title', 'N/A')}\n"
            f"Subreddit: {opp.get('subreddit', 'unknown')}\n"
            f"URL: {opp.get('url', 'N/A')}\n"
            f"Content preview: {opp.get('content', 'N/A')[:300]}\n"
            f"Type: {opp.get('type', 'post')}\n"
        )

    messages = [
        SystemMessage(content=DISCOVERY_SYSTEM_PROMPT),
        HumanMessage(content=(
            f"Project Brief:\n{brief.to_prompt_str()}\n\n"
            f"Reddit Items Found:\n{posts_text}"
        )),
    ]

    try:
        structured_llm = llm.with_structured_output(OpportunityList)
        response = structured_llm.invoke(messages)
        scored = [opp.model_dump() for opp in response.opportunities]

        # Safety net: recompute total_score from sub-scores in case AI gets it wrong
        for item in scored:
            item["total_score"] = item.get("relevance", 0) + item.get("intent", 0)
            item["opportunity_type"] = "reply_post"
            if "subreddit" in item:
                item["subreddit"] = _clean_subreddit(item["subreddit"])

        filtered = [s for s in scored if s.get("total_score", 0) >= 8]
        return sorted(filtered, key=lambda x: x.get("total_score", 0), reverse=True)
    except Exception as e:
        print(f"Error scoring opportunities: {e}")
        return []


def discover_subreddit_opportunities(llm, brief, reddit_evidence, max_subreddits=5):
    """
    Convert Reddit search evidence into subreddit-level opportunities for original posts.
    """
    if not reddit_evidence:
        return []

    by_subreddit = {}
    for opp in reddit_evidence:
        sub = _clean_subreddit(opp.get("subreddit", "unknown"))
        if not sub or sub == "unknown":
            continue
        by_subreddit.setdefault(sub, []).append(opp)

    evidence_text = ""
    for sub, items in sorted(
        by_subreddit.items(),
        key=lambda kv: sum(i.get("total_score", 0) for i in kv[1]),
        reverse=True,
    )[:12]:
        evidence_text += f"\n## r/{sub}\n"
        for item in sorted(items, key=lambda x: x.get("total_score", 0), reverse=True)[:4]:
            evidence_text += (
                f"- {item.get('title', 'Untitled')} "
                f"(score {item.get('total_score', '?')}, type {item.get('opportunity_type', 'reply_post')})\n"
                f"  URL: {item.get('url', '')}\n"
                f"  Why: {item.get('reasoning', '')}\n"
            )

    messages = [
        SystemMessage(content=SUBREDDIT_DISCOVERY_PROMPT),
        HumanMessage(content=(
            f"Project Brief:\n{brief.to_prompt_str()}\n\n"
            f"Discovered Reddit evidence by subreddit:\n{evidence_text}"
        )),
    ]

    try:
        structured_llm = llm.with_structured_output(SubredditOpportunityList)
        response = structured_llm.invoke(messages)
        opportunities = [opp.model_dump() for opp in response.opportunities]
        for item in opportunities:
            item["subreddit"] = _clean_subreddit(item.get("subreddit", "unknown"))
            item["total_score"] = item.get("relevance", 0) + item.get("intent", 0)
            item["opportunity_type"] = "new_post"
            item["type"] = "post"
            item["source"] = "subreddit_discovery"
            item.setdefault("url", f"https://www.reddit.com/r/{item['subreddit']}/")
            item.setdefault("title", f"Create a post in r/{item['subreddit']}")

        filtered = [s for s in opportunities if s.get("total_score", 0) >= 10]
        return sorted(filtered, key=lambda x: x.get("total_score", 0), reverse=True)[:max_subreddits]
    except Exception as e:
        print(f"Error discovering subreddits: {e}")
        return []


def collect_reddit_evidence(tavily_api_key, queries, max_results_per_query=5, time_range="month", search_method="reddit_json"):
    """Search Reddit and return normalized raw evidence without LLM scoring."""
    from reddit_marketing.reddit_search import search_reddit, search_reddit_json

    all_results = []
    seen_urls = set()

    for query in queries:
        if search_method == "reddit_json":
            results = search_reddit_json(query, max_results=max_results_per_query, time_range=time_range)

        else:
            results = search_reddit(
                tavily_api_key,
                query,
                max_results=max_results_per_query,
                time_range=time_range,
            )

        if not results and search_method != "tavily" and tavily_api_key:
            import streamlit as st
            st.warning(f"Reddit JSON rate-limited for query: '{query}'. Falling back to Tavily...")
            results = search_reddit(
                tavily_api_key,
                query,
                max_results=max_results_per_query,
                time_range=time_range,
            )

        for result in results:
            url = result.get("url")
            if url and url not in seen_urls:
                seen_urls.add(url)
                all_results.append(result)

    return all_results


def score_comment_opportunities(llm, brief, comments):
    """Wrap all fetched comments into opportunity format without any LLM scoring or cutoff."""
    if not comments:
        return []

    enriched = []
    for comment in comments:
        item = {
            "id": comment.get("id", ""),
            "subreddit": _clean_subreddit(comment.get("subreddit", "unknown")),
            "total_score": comment.get("score", 0),
            "opportunity_type": "comment_reply",
            "type": "comment_reply",
            "source": "reddit_json_monitor",
            "comment": comment,
            "url": comment.get("permalink", ""),
            "title": f"Reply to comment on {comment.get('post_title', 'Reddit post')}",
            "reasoning": "",
            "relevance": 0,
            "intent": 0,
        }
        enriched.append(item)

    return enriched


def run_discovery(
    llm,
    tavily_api_key,
    brief,
    queries,
    max_results_per_query=5,
    time_range="month",
    search_method="tavily",
    rss_subreddits=None,
):
    """
    Discovery pipeline:
    1. Search Reddit via Tavily, Reddit JSON, 
    2. Score and rank all results.

    Returns a list of scored_opportunities.
    """
    all_results = collect_reddit_evidence(
        tavily_api_key,
        queries,
        max_results_per_query=max_results_per_query,
        time_range=time_range,
        search_method=search_method,
    )
    scored = score_opportunities(llm, brief, all_results)
    return scored


def run_subreddit_discovery(
    llm,
    tavily_api_key,
    brief,
    queries,
    max_results_per_query=5,
    time_range="month",
    search_method="reddit_json",
    rss_subreddits=None,
    max_subreddits=5,
):
    """
    Separate pipeline for finding subreddits to create original posts in.
    It searches Reddit for evidence, then returns only subreddit opportunities.
    """
    evidence = collect_reddit_evidence(
        tavily_api_key,
        queries,
        max_results_per_query=max_results_per_query,
        time_range=time_range,
        search_method=search_method,
    )
    return discover_subreddit_opportunities(llm, brief, evidence, max_subreddits=max_subreddits)
