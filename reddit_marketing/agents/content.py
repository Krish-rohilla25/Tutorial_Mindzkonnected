"""
Content Agent — generates Reddit post and reply drafts.

Takes an opportunity (with strategy) and the project brief, produces
ready-to-review content matching the subreddit's voice.
"""

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field


class ReplyDraft(BaseModel):
    body: str = Field(description="your reply text")
    context: str = Field(description="one sentence summary of what you're replying to")


class PostDraft(BaseModel):
    title: str = Field(description="Reddit post title")
    body: str = Field(description="Reddit post body")
    context: str = Field(description="one sentence summary of why this subreddit/post fits")


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


POST_SYSTEM_PROMPT = """You are drafting an original Reddit post for a specific subreddit.

Write in the style of a curious person starting a sincere community discussion, like:
- a plain question title
- an optional short flair-like subtitle/category
- a few short paragraphs describing a specific observation or situation
- a final question asking the community for their perspective

The post should feel native to Reddit and similar to a travel/community question such as:
"Is football culture in Mexico always like what I'm seeing during the World Cup?"
It should describe a concrete experience, name what surprised the writer, and ask whether that pattern is normal.

Rules:
- Do not write an ad, launch announcement, feature list, or polished marketing copy.
- Do not include the product name unless it is genuinely necessary; if used, make it incidental.
- Do not use bullets, headings, slogans, CTAs, links, emojis, or hype.
- Do not overclaim or pretend certainty.
- Use first person when natural: "I've noticed...", "I'm wondering...", "I wasn't expecting..."
- Keep it human, slightly imperfect, and discussion-led.
- The title should be a real question someone in that subreddit might ask.

Respond by strictly following the requested JSON schema."""


def _clean_subreddit(sub: str) -> str:
    """Normalize subreddit name — strip any leading r/ prefixes."""
    sub = sub.strip()
    while sub.startswith("r/"):
        sub = sub[2:]
    return sub


def generate_draft(llm, brief, opportunity, feedback=None):
    """
    Generate a post or reply draft for a Reddit opportunity.

    opportunity: dict with strategy fields + original post content
    feedback: optional user feedback to improve the draft
    Returns a draft dict: {body, context, opportunity, draft_type, subreddit, title}
    """
    content_type = opportunity.get("content_type") or opportunity.get("opportunity_type", "reply")
    if content_type in {"new_post", "post"}:
        return generate_post_draft(llm, brief, opportunity, feedback=feedback)
    if content_type == "comment_reply":
        return generate_comment_reply_draft(llm, brief, opportunity, feedback=feedback)

    human_content = (
        f"Product Brief:\n{brief.to_prompt_str()}\n\n"
        f"Thread context:\n"
        f"Subreddit: r/{_clean_subreddit(opportunity.get('subreddit', 'unknown'))}\n"
        f"Post Title: {opportunity.get('title', 'N/A')}\n"
        f"Post URL: {opportunity.get('url', 'N/A')}\n"
        f"Post preview: {opportunity.get('content', '')[:300]}\n"
        f"\nYour Angle: {opportunity.get('angle', 'helpful_tip')}\n"
        f"Approach: {opportunity.get('approach', 'Be helpful and natural')}\n"
        f"Key Points to work in naturally:\n"
        + "\n".join(f"- {p}" for p in opportunity.get("key_points", []))
        + f"\n\nCaution: {opportunity.get('caution', 'None')}"
    )

    if feedback:
        human_content += f"\n\nUSER FEEDBACK ON PREVIOUS DRAFT:\nThe user rejected the previous draft and provided this feedback to improve it:\n\"{feedback}\"\n\nPlease write a completely new draft that strictly incorporates this feedback."

    messages = [
        SystemMessage(content=REPLY_SYSTEM_PROMPT),
        HumanMessage(content=human_content),
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
        print(f"Error generating draft: {e}")
        return {
            "title": opportunity.get("title", "Reply"),
            "body": "Generation failed. Please try again.",
            "context": opportunity.get("title", ""),
            "subreddit": _clean_subreddit(opportunity.get("subreddit", "unknown")),
            "opportunity": opportunity,
            "draft_type": "reply",
        }


def generate_post_draft(llm, brief, opportunity, feedback=None):
    """Generate an original post draft for a subreddit."""
    subreddit = _clean_subreddit(opportunity.get("subreddit", "unknown"))
    evidence = opportunity.get("evidence", [])

    human_content = (
        f"Product Brief:\n{brief.to_prompt_str()}\n\n"
        f"Target subreddit: r/{subreddit}\n"
        f"Subreddit opportunity: {opportunity.get('title', 'Create a useful post')}\n"
        f"Why this subreddit fits: {opportunity.get('reasoning', '')}\n"
        f"Strategy angle: {opportunity.get('angle', 'discussion_starter')}\n"
        f"Approach: {opportunity.get('approach', 'Create a helpful discussion post')}\n"
        f"Key Points to work in naturally:\n"
        + "\n".join(f"- {p}" for p in opportunity.get("key_points", []))
        + "\n\nEvidence from recent Reddit threads:\n"
        + "\n".join(f"- {item}" for item in evidence)
        + f"\n\nCaution: {opportunity.get('caution', 'None')}"
    )

    if feedback:
        human_content += f"\n\nUSER FEEDBACK ON PREVIOUS DRAFT:\n\"{feedback}\"\n\nPlease write a new version that incorporates this feedback."

    messages = [
        SystemMessage(content=POST_SYSTEM_PROMPT),
        HumanMessage(content=human_content),
    ]

    try:
        structured_llm = llm.with_structured_output(PostDraft)
        response = structured_llm.invoke(messages)
        draft = response.model_dump()
        draft["opportunity"] = opportunity
        draft["draft_type"] = "post"
        draft["subreddit"] = subreddit
        return draft
    except Exception as e:
        print(f"Error generating post draft: {e}")
        return {
            "title": opportunity.get("title", "Post Draft"),
            "body": "Generation failed. Please try again.",
            "context": opportunity.get("reasoning", ""),
            "subreddit": subreddit,
            "opportunity": opportunity,
            "draft_type": "post",
        }


def generate_comment_reply_draft(llm, brief, opportunity, feedback=None):
    """Generate a reply draft for a monitored comment."""
    comment = opportunity.get("comment", {})
    subreddit = _clean_subreddit(opportunity.get("subreddit") or comment.get("subreddit", "unknown"))

    human_content = (
        f"Product Brief:\n{brief.to_prompt_str()}\n\n"
        f"Thread context:\n"
        f"Subreddit: r/{subreddit}\n"
        f"Post Title: {comment.get('post_title', opportunity.get('title', 'N/A'))}\n"
        f"Post URL: {comment.get('post_url', 'N/A')}\n"
        f"Post preview: {comment.get('post_body', '')[:300]}\n\n"
        f"Comment to reply to:\n"
        f"Author: {comment.get('author', 'unknown')}\n"
        f"Comment URL: {comment.get('permalink', opportunity.get('url', ''))}\n"
        f"Comment: {comment.get('body', '')[:1000]}\n\n"
        f"Your Angle: {opportunity.get('angle', 'direct_answer')}\n"
        f"Approach: {opportunity.get('approach', 'Reply helpfully and naturally')}\n"
        f"Key Points to work in naturally:\n"
        + "\n".join(f"- {p}" for p in opportunity.get("key_points", []))
        + f"\n\nCaution: {opportunity.get('caution', 'None')}"
    )

    if feedback:
        human_content += f"\n\nUSER FEEDBACK ON PREVIOUS DRAFT:\n\"{feedback}\"\n\nPlease write a new version that incorporates this feedback."

    messages = [
        SystemMessage(content=REPLY_SYSTEM_PROMPT),
        HumanMessage(content=human_content),
    ]

    try:
        structured_llm = llm.with_structured_output(ReplyDraft)
        response = structured_llm.invoke(messages)
        draft = response.model_dump()
        draft["opportunity"] = opportunity
        draft["draft_type"] = "comment_reply"
        draft["subreddit"] = subreddit
        draft["title"] = opportunity.get("title", "Comment Reply")
        return draft
    except Exception as e:
        print(f"Error generating comment reply: {e}")
        return {
            "title": opportunity.get("title", "Comment Reply"),
            "body": "Generation failed. Please try again.",
            "context": comment.get("body", ""),
            "subreddit": subreddit,
            "opportunity": opportunity,
            "draft_type": "comment_reply",
        }
