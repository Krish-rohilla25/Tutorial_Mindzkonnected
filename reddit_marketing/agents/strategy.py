"""
Strategy Agent — picks the angle and approach for each opportunity.

Decides *how* to engage: helpful tip, direct answer, personal story, etc.
Also handles deduplication and spam prevention.
"""

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

class Strategy(BaseModel):
    title: str
    url: str
    subreddit: str
    total_score: int
    angle: str = Field(description='One of: "helpful_tip", "direct_answer", "personal_experience", "resource_share", "discussion_starter"')
    approach: str = Field(description="A 1-2 sentence description of how to approach this specific post/reply")
    content_type: str = Field(description='"new_post" or "reply"')
    key_points: list[str] = Field(description="2-3 bullet points of what the content should cover")
    caution: str = Field(description="Any warnings (e.g. strict self-promo rules)")
    skip: bool = Field(description="Set to true if this opportunity should be dropped")

class StrategyList(BaseModel):
    strategies: list[Strategy]

STRATEGY_SYSTEM_PROMPT = """You are a Reddit engagement strategist. Given a product brief and a list of scored Reddit opportunities, decide the best approach for each one.

For each opportunity, provide:
- **angle**: The engagement angle. One of: "helpful_tip", "direct_answer", "personal_experience", "resource_share", "discussion_starter"
- **approach**: A 1-2 sentence description of how to approach this specific post/reply.
- **content_type**: "new_post" (create a post in the subreddit) or "reply" (reply to the existing thread).
- **key_points**: 2-3 bullet points of what the content should cover.
- **caution**: Any warnings (e.g. "this sub has strict self-promo rules").

Rules:
- NEVER suggest directly advertising. The tone must be genuinely helpful.
- If someone is asking for recommendations, suggest the product as ONE option among others.
- For "personal_experience" angles, the post should read like a real person sharing what worked for them.
- Skip opportunities that would feel forced or spammy.

Respond by strictly following the requested JSON schema.
Set "skip": true for opportunities that should be dropped (with a reason in "caution")."""

def plan_strategy(llm, brief, scored_opportunities):
    """
    For each scored opportunity, pick an engagement angle and approach.

    Returns a list of enriched opportunity dicts with strategy fields.
    """
    if not scored_opportunities:
        return []
    
    opps_text = ""
    for i, opp in enumerate(scored_opportunities, 1):
        opps_text += (
            f"\n--- Opportunity {i} ---\n"
            f"Title: {opp.get('title', 'N/A')}\n"
            f"Subreddit: r/{opp.get('subreddit', 'unknown')}\n"
            f"URL: {opp.get('url', 'N/A')}\n"
            f"Score: {opp.get('total_score', 'N/A')}\n"
            f"Reasoning: {opp.get('reasoning', 'N/A')}\n"
            f"Type: {opp.get('opportunity_type', 'post')}\n"
        )

    messages = [
        SystemMessage(content=STRATEGY_SYSTEM_PROMPT),
        HumanMessage(content=(
            f"Project Brief:\n{brief.to_prompt_str()}\n\n"
            f"Scored Opportunities:\n{opps_text}"
        )),
    ]

    try:
        structured_llm = llm.with_structured_output(StrategyList)
        response = structured_llm.invoke(messages)
        strategies = [s.model_dump() for s in response.strategies]
        
        # Filter out skipped opportunities
        return [s for s in strategies if not s.get("skip", False)]
    except Exception as e:
        print(f"Error generating strategies: {e}")
        return scored_opportunities






