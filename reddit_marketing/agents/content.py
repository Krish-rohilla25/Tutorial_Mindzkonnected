"""
Content Agent — generates post drafts and reply drafts.

Takes an opportunity (with strategy) and the project brief, produces
ready-to-post content matching the subreddit's voice.
"""

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field


class ReplyDraft(BaseModel):
    body: str = Field(description="your reply text")
    context: str = Field(description="one sentence summary of what you're replying to")




REPLY_SYSTEM_PROMPT = """You are a real Reddit user replying to a thread. You have personal experience with this product and you're sharing it genuinely — not promoting it. You care more about actually helping the person than mentioning the product.

Your reply style:
- Short to medium length — Reddit doesn't reward essays
- Get to the point fast, answer their actual question in the first sentence
- Sound like a real person who typed this quickly, not a content writer
- The product mention should feel almost like an afterthought, not the main point
- Be honest — if the product has a downside or isn't perfect for their use case, say so
- Use natural speech patterns: sentence fragments, contractions, casual tone
- Don't bullet-point everything — write like you talk

Anti-AI checklist — do NOT:
- Start with "Great question!" or "Absolutely!" or "Certainly!"
- Use "I hope this helps!" or similar closers
- Use "leverage", "utilize", "delve into", "robust", "seamless"
- Write in perfect parallel structure
- Mention multiple features of the product
- Sound enthusiastic about everything

DO:
- Sound slightly tired or casual — like you're helping someone between tasks
- Pick ONE thing about the product to mention, not a feature list
- Maybe admit you weren't sure it would work at first
- If it fits, throw in a completely unrelated tip that shows you actually know the subject

Respond by strictly following the requested JSON schema."""


def _clean_subreddit(sub: str) -> str:
    """Normalize subreddit name — strip any leading r/ prefixes."""
    sub = sub.strip()
    while sub.startswith("r/"):
        sub = sub[2:]
    return sub




def generate_reply_draft(llm, brief, opportunity):
    """
    Generate a reply draft for an existing Reddit thread or top comment.

    opportunity: dict with strategy fields + original post/comment content
    Returns a dict: {body, context, opportunity, draft_type}
    """
    # Check if this is a comment-level reply
    is_comment = opportunity.get("reply_to_comment", False)
    comment_context = ""
    if is_comment:
        comment_context = (
            f"\nTop Comment you're specifically replying to:\n"
            f"\"{opportunity.get('comment_body', '')}\"\n"
            f"(This comment has {opportunity.get('comment_score', '?')} upvotes)\n"
        )

    messages = [
        SystemMessage(content=REPLY_SYSTEM_PROMPT),
        HumanMessage(content=(
            f"Product Brief:\n{brief.to_prompt_str()}\n\n"
            f"Thread context:\n"
            f"Subreddit: r/{_clean_subreddit(opportunity.get('subreddit', 'unknown'))}\n"
            f"Post Title: {opportunity.get('title', 'N/A')}\n"
            f"Post URL: {opportunity.get('url', 'N/A')}\n"
            f"Post preview: {opportunity.get('content', '')[:300]}\n"
            + comment_context
            + f"\nYour Angle: {opportunity.get('angle', 'helpful_tip')}\n"
            f"Approach: {opportunity.get('approach', 'Be helpful and natural')}\n"
            f"Key Points to work in naturally:\n"
            + "\n".join(f"- {p}" for p in opportunity.get("key_points", []))
            + f"\n\nCaution: {opportunity.get('caution', 'None')}"
        )),
    ]

    try:
        structured_llm = llm.with_structured_output(ReplyDraft)
        response = structured_llm.invoke(messages)
        draft = response.model_dump()
        
        draft["opportunity"] = opportunity
        draft["draft_type"] = "reply"
        draft["subreddit"] = _clean_subreddit(opportunity.get("subreddit", "unknown"))
        draft["title"] = opportunity.get("title", "Reply")
        return draft
    except Exception as e:
        print(f"Error generating reply draft: {e}")
        return {
            "title": opportunity.get("title", "Reply"),
            "body": "Generation failed. Please try again.",
            "context": opportunity.get("title", ""),
            "subreddit": _clean_subreddit(opportunity.get("subreddit", "unknown")),
            "opportunity": opportunity,
            "draft_type": "reply",
        }


def generate_draft(llm, brief, opportunity):
    """
    Generate a reply draft.
    """
    return generate_reply_draft(llm, brief, opportunity)



