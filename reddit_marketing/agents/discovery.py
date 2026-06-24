"""
Discovery Agent 

Uses Tavily to search Reddit posts AND top comments, then the LLM scores and ranks.
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
    freshness: int
    total_score: int
    reasoning: str
    opportunity_type: str = Field(description="'new_post' or 'reply_post' or 'reply_comment'")

class OpportunityList(BaseModel):
    opportunities: list[ScoredOpportunity]


DISCOVERY_SYSTEM_PROMPT = """You are a Reddit marketing strategist. Your job is to find the best opportunities to promote a product on Reddit in a helpful, non-spammy way.

You will receive:
1. A project brief describing the product.
2. A list of Reddit posts/threads/comments found via search.

For each item, score it on three dimensions (0-10):
- **relevance**: How related is this post/comment to the product?
- **intent**: Is someone asking for help, recommendations, or solutions that the product could address?
- **freshness**: Grade STRICTLY based on timestamps visible in the text (e.g., "1d ago", "18 days ago"). Use this scale: 
  - Within 24 hours = 10
  - 2 to 3 days ago = 9
  - 4 to 7 days ago = 8
  - 1 to 2 weeks ago = 6
  - 3 to 4 weeks ago = 4
  - Older than 1 month = 2
  - If no timestamp is visible anywhere, default to 7.

Also provide:
- **reasoning**: A one-sentence explanation of why this is (or isn't) a good opportunity.
- **opportunity_type**: 
  - "new_post" if we should create a new original post in this subreddit
  - "reply_post" if we should reply directly to this thread/post
  - "reply_comment" if we should reply to a specific top comment in this thread

IMPORTANT: The subreddit name in your response must be ONLY the subreddit name with NO r/ prefix.
Example: "studytips" NOT "r/studytips"

Respond by strictly following the requested JSON schema. Each opportunity must have:
- title: original post title
- url: original url
- subreddit: subreddit name only — NO r/ prefix
- relevance: 0-10
- intent: 0-10
- freshness: 0-10
- total_score: sum of the above (0-30)
- reasoning: one-sentence explanation
- opportunity_type: "new_post" or "reply_post" or "reply_comment"

Sort your internal list by total_score descending. Only include opportunities with total_score >= 12."""


def _clean_subreddit(sub: str) -> str:
    """Normalize — strip any leading r/ prefix."""
    sub = sub.strip()
    while sub.startswith("r/"):
        sub = sub[2:]
    return sub


def generate_search_queries(llm, brief):
    """
    Use the LLM to generate smart search queries from the project brief.
    Returns a list of (query_string, search_focus) tuples.
    search_focus is either 'posts' or 'comments'.
    """
    messages = [
        SystemMessage(content=(
            "You are a Reddit marketing expert. Given a product brief, generate "
            "6-10 search queries that would find Reddit posts AND comment threads "
            "where this product could be genuinely helpful. Think about:\n"
            "- Problems the product solves (people asking for help)\n"
            "- Questions people commonly ask in the target audience's subreddits\n"
            "- Subreddits where the target audience hangs out\n"
            "- Threads with high engagement about related topics\n"
            "- Top comments in relevant threads discussing similar tools\n\n"
            "Respond with ONLY a JSON array of query strings. No markdown fences."
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
        # Show comment context if available
        comment_info = ""
        if opp.get("top_comments"):
            top = opp["top_comments"][0]
            comment_info = f"\nTop comment ({top.get('score','?')} upvotes): \"{top.get('body','')[:200]}\""

        posts_text += (
            f"\n--- Item {i} ---\n"
            f"Title: {opp.get('title', 'N/A')}\n"
            f"Subreddit: {opp.get('subreddit', 'unknown')}\n"
            f"URL: {opp.get('url', 'N/A')}\n"
            f"Content preview: {opp.get('content', 'N/A')[:300]}\n"
            f"Type: {opp.get('type', 'post')}\n"
            + comment_info + "\n"
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
            item["total_score"] = item.get("relevance", 0) + item.get("intent", 0) + item.get("freshness", 0)
            # Clean subreddit names
            if "subreddit" in item:
                item["subreddit"] = _clean_subreddit(item["subreddit"])
                
        filtered = [s for s in scored if s.get("total_score", 0) >= 12]
        return sorted(filtered, key=lambda x: x.get("total_score", 0), reverse=True)
    except Exception as e:
        print(f"Error scoring opportunities: {e}")
        return []  # Return empty list so UI shows a clean error instead of unscored garbage


def run_discovery(llm, tavily_api_key, brief, extra_queries=None, max_results_per_query=5, time_range="month"):
    """
    Full discovery pipeline:
    1. Generate search queries from the brief.
    2. Search Reddit posts AND comment threads via Tavily.
    3. For comment-thread results, extract top comments from content.
    4. Score and rank all results.

    Returns (queries_used, scored_opportunities).
    """
    from reddit_marketing.reddit_search import search_reddit, search_top_comments

    # Step 1: Generate queries
    queries = generate_search_queries(llm, brief)
    if extra_queries:
        queries.extend(extra_queries)

    # Step 2: Search Reddit
    all_results = []
    seen_urls = set()

    for query in queries:
        # Regular post/thread search
        results = search_reddit(tavily_api_key, query, max_results=max_results_per_query, time_range=time_range)
        for r in results:
            if r["url"] not in seen_urls:
                seen_urls.add(r["url"])
                all_results.append(r)

        # Comment-focused search — finds threads with top comments
        comment_results = search_top_comments(tavily_api_key, query, max_results=max(3, max_results_per_query//2), time_range=time_range)
        for r in comment_results:
            if r["url"] not in seen_urls:
                seen_urls.add(r["url"])
                all_results.append(r)

    # Step 3: Score and rank
    scored = score_opportunities(llm, brief, all_results)

    return queries, scored



