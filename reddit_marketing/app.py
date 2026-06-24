"""
Reddit Marketing Agent — Streamlit Dashboard

Run with: uv run streamlit run reddit_marketing/app.py
"""

import sys
import os
from pathlib import Path

_parent = str(Path(__file__).resolve().parent.parent)
if _parent not in sys.path:
    sys.path.insert(0, _parent)

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

from reddit_marketing.config import (
    ProjectBrief,
    get_default_brief,
    get_groq_api_key,
    get_google_api_key,
    get_tavily_api_key,
)
from reddit_marketing.llm_handler import (
    get_llm,
    GROQ_MODELS,
    GEMINI_MODELS,
    DEFAULT_PROVIDER,
    DEFAULT_MODEL,
)
from reddit_marketing.agents.discovery import run_discovery
from reddit_marketing.agents.strategy import plan_strategy
from reddit_marketing.agents.content import generate_draft
from reddit_marketing.publisher import copy_and_open, get_submit_url, get_reply_url
from reddit_marketing import storage

# Initialize database
storage.init_db()


# ── Page config ──────────────────────────────────────────────────────────

st.set_page_config(page_title="Reddit Marketing Agent", layout="wide")
st.title("Reddit Marketing Agent")
st.caption("Discover → Strategize → Draft → Publish")


# ── Sidebar: LLM + Tavily settings ──────────────────────────────────────

st.sidebar.header(" Settings")

provider = st.sidebar.selectbox("LLM Provider", ["Groq", "Gemini"], index=0)

if provider == "Groq":
    model_options = GROQ_MODELS
    default_key = get_groq_api_key()
else:
    model_options = GEMINI_MODELS
    default_key = get_google_api_key()

model_name = st.sidebar.selectbox("Model", model_options)

api_key = st.sidebar.text_input(
    "LLM API Key",
    value=default_key,
    type="password",
    placeholder=f"Enter your {provider} API key",
)

st.sidebar.markdown("---")

tavily_key = st.sidebar.text_input(
    "Tavily API Key",
    value=get_tavily_api_key(),
    type="password",
    placeholder="Enter your Tavily API key",
)

# Connection status
if tavily_key:
    st.sidebar.success("Tavily connected — Reddit search ready")
else:
    st.sidebar.warning("No Tavily key — search won't work")

if api_key:
    st.sidebar.success(f"{provider} LLM connected")
else:
    st.sidebar.warning(f"No {provider} API key")

st.sidebar.markdown("---")
st.sidebar.subheader(" Project Management")

# Project Loading & Saving
all_projects = storage.get_all_projects()
new_project_name = st.sidebar.text_input("New Project Name", placeholder="e.g. Acme App")
if st.sidebar.button("Create New Project"):
    if new_project_name:
        st.session_state.project_name = new_project_name
        st.session_state.brief = get_default_brief()
        st.session_state.brief.brand_name = new_project_name
        st.session_state.discovery_results = []
        st.session_state.search_queries = []
        st.session_state.strategy_results = []
        st.session_state.drafts = []
        storage.save_project(new_project_name, st.session_state.brief.__dict__, {
            "search_queries": [],
            "discovery_results": [],
            "strategy_results": [],
            "drafts": []
        })
        st.rerun()

if all_projects:
    selected_project = st.sidebar.selectbox("Load Project", ["-- Select --"] + all_projects, index=0)
    if selected_project != "-- Select --":
        if st.sidebar.button(f"Load {selected_project}"):
            brief_dict, state_dict = storage.load_project(selected_project)
            st.session_state.project_name = selected_project
            st.session_state.brief = ProjectBrief(**brief_dict)
            st.session_state.search_queries = state_dict.get("search_queries", [])
            st.session_state.discovery_results = state_dict.get("discovery_results", [])
            st.session_state.strategy_results = state_dict.get("strategy_results", [])
            st.session_state.drafts = state_dict.get("drafts", [])
            # Restore URL sets (stored as lists in DB)
            st.session_state.new_opportunity_urls = set(state_dict.get("new_opportunity_urls", []))
            st.session_state.new_strategy_urls = set(state_dict.get("new_strategy_urls", []))
            st.session_state.new_draft_urls = set(state_dict.get("new_draft_urls", []))
            st.session_state.published_urls = set(state_dict.get("published_urls", []))
            st.rerun()

st.sidebar.markdown("---")
if st.sidebar.button("Reset All"):
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()

# ── Session state ────────────────────────────────────────────────────────

if "project_name" not in st.session_state:
    st.session_state.project_name = "Default Project"

if "brief" not in st.session_state:
    st.session_state.brief = get_default_brief()

if "discovery_results" not in st.session_state:
    st.session_state.discovery_results = []

if "search_queries" not in st.session_state:
    st.session_state.search_queries = []

if "strategy_results" not in st.session_state:
    st.session_state.strategy_results = []

if "drafts" not in st.session_state:
    st.session_state.drafts = []

# Track which items are "new" (from the latest run) vs "old" (from previous runs)
if "new_opportunity_urls" not in st.session_state:
    st.session_state.new_opportunity_urls = set()
if "new_strategy_urls" not in st.session_state:
    st.session_state.new_strategy_urls = set()
if "new_draft_urls" not in st.session_state:
    st.session_state.new_draft_urls = set()
# Track which opportunity URLs have been published
if "published_urls" not in st.session_state:
    st.session_state.published_urls = set()

def save_current_state():
    """Helper to dump current state to DB for the active project."""
    state_dict = {
        "search_queries": st.session_state.search_queries,
        "discovery_results": st.session_state.discovery_results,
        "strategy_results": st.session_state.strategy_results,
        "drafts": st.session_state.drafts,
        # Store sets as lists (JSON serializable)
        "new_opportunity_urls": list(st.session_state.new_opportunity_urls),
        "new_strategy_urls": list(st.session_state.new_strategy_urls),
        "new_draft_urls": list(st.session_state.new_draft_urls),
        "published_urls": list(st.session_state.published_urls),
    }
    storage.save_project(st.session_state.project_name, st.session_state.brief.__dict__, state_dict)


# ── Tabs ─────────────────────────────────────────────────────────────────

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "Project Brief",
    "Discovery",
    "Strategy & Content",
    "Publish",
    "History"
])


# ═══════════════════════════════════════════════════════════════════════
# TAB 1: Project Brief
# ═══════════════════════════════════════════════════════════════════════

with tab1:
    st.subheader("Define Your Project")
    st.write("Fill in the details about your product. This drives everything the agents generate.")

    brief = st.session_state.brief

    brand_name = st.text_input("Brand Name", value=brief.brand_name)
    description = st.text_area("Description", value=brief.description, height=100)
    features_str = st.text_area(
        "Key Features (one per line)",
        value="\n".join(brief.features),
        height=120,
    )
    target_audience = st.text_input("Target Audience", value=brief.target_audience)
    voice_tone = st.text_input("Voice / Tone", value=brief.voice_tone)

    if st.button("Save Brief", type="primary"):
        st.session_state.brief = ProjectBrief(
            brand_name=brand_name,
            description=description,
            features=[f.strip() for f in features_str.split("\n") if f.strip()],
            target_audience=target_audience,
            voice_tone=voice_tone,
        )
        save_current_state()
        st.success(f"Brief saved to project '{st.session_state.project_name}'!")

    # Show current brief as the LLM sees it
    with st.expander("Preview: How the LLM sees your brief"):
        st.code(st.session_state.brief.to_prompt_str())


# ═══════════════════════════════════════════════════════════════════════
# TAB 5: History
# ═══════════════════════════════════════════════════════════════════════

with tab5:
    st.subheader(f"History for '{st.session_state.project_name}'")
    st.write("A log of all replies and posts you've published for this project.")

    history_log = storage.get_published_log(st.session_state.project_name)

    if not history_log:
        st.info("No published posts found for this project yet.")
    else:
        st.success(f"Found {len(history_log)} published items.")
        for item in history_log:
            published_at = item.get("published_at", "Unknown Date")
            draft_type = item.get("draft_type", "reply")
            sub = item.get("subreddit", "unknown")
            url = item.get("url", "#")
            content = item.get("content", "")

            label = f"[{published_at}] r/{sub} ({draft_type})"
            with st.expander(label):
                st.markdown(f"**URL:** [{url}]({url})")
                st.markdown("**Content:**")
                st.text(content)


# ═══════════════════════════════════════════════════════════════════════
# TAB 2: Discovery
# ═══════════════════════════════════════════════════════════════════════

with tab2:
    st.subheader("Find Reddit Opportunities")
    st.write("The Discovery Agent searches Reddit for posts where your product can genuinely help.")

    # Optional extra queries
    extra = st.text_input(
        "Extra search queries (optional, comma-separated)",
        placeholder="e.g. best study apps, AI flashcard maker",
    )
    extra_queries = [q.strip() for q in extra.split(",") if q.strip()] if extra else None

    col_opts1, col_opts2 = st.columns(2)
    with col_opts1:
        time_range = st.selectbox(
            "Time Range (Find freshest posts)",
            options=["day", "week", "month", "year", "all"],
            index=2, # defaults to month
            format_func=lambda x: "Past 24 hours" if x == "day" else f"Past {x}" if x != "all" else "Any time"
        )
    with col_opts2:
        max_total = st.slider("Max total opportunities to find", min_value=1, max_value=30, value=10)

    tr_param = None if time_range == "all" else time_range

    st.write("") # spacer
    run_discovery_btn = st.button("Run Discovery", type="primary")

    if run_discovery_btn:
        if not api_key or not tavily_key:
            st.error("Please set both LLM and Tavily API keys in the sidebar.")
        else:
            with st.spinner("Generating search queries and scanning Reddit..."):
                try:
                    llm = get_llm(provider, model_name, api_key)

                    queries, results = run_discovery(
                        llm, tavily_key, st.session_state.brief, extra_queries,
                        max_results_per_query=5, time_range=tr_param
                    )

                    st.session_state.search_queries = queries
                    
                    # Merge new results on top, keeping old ones below (deduplicate by URL)
                    existing = st.session_state.discovery_results
                    existing_urls = {o.get("url") for o in existing}
                    fresh = [r for r in results[:max_total] if r.get("url") not in existing_urls]
                    st.session_state.new_opportunity_urls = {r.get("url") for r in fresh}
                    st.session_state.discovery_results = fresh + existing
                    
                    save_current_state()

                except Exception as e:
                    st.error(f"Discovery failed: {str(e)}")

    # Show search queries used
    if st.session_state.search_queries:
        with st.expander(f" Search queries used ({len(st.session_state.search_queries)})"):
            for q in st.session_state.search_queries:
                st.write(f"• {q}")

    # Show results
    if st.session_state.discovery_results:
        new_urls = st.session_state.new_opportunity_urls
        published_urls = st.session_state.published_urls

        new_opps = [o for o in st.session_state.discovery_results if o.get("url") in new_urls]
        old_opps = [o for o in st.session_state.discovery_results if o.get("url") not in new_urls]

        def render_opportunity(opp, i, allow_strategy=True, default_checked=True):
            score = opp.get("total_score", "?")
            title = opp.get("title", "Untitled")
            sub = opp.get("subreddit", "unknown")
            reasoning = opp.get("reasoning", "")
            url = opp.get("url", "")
            opp_type = opp.get("opportunity_type", "reply")

            if isinstance(score, (int, float)):
                score_color = "🟢" if score >= 24 else ("🟡" if score >= 18 else "🔴")
            else:
                score_color = "⚪"

            opp_type_label = {
                "new_post": " New Post",
                "reply_post": "Reply to Thread",
                "reply_comment": "Reply to Top Comment",
            }.get(opp_type, "Reply to Thread")

            clean_sub = sub.lstrip("r/") if sub.startswith("r/") else sub
            source_badge = "RSS" if opp.get('source') == 'rss' else ("Comments" if opp.get('source') == 'tavily_comments' else "Post")
            published_badge = " Published" if url in published_urls else ""

            with st.expander(f"{score_color} [{score}/30] r/{clean_sub} — {title}{published_badge}"):
                st.write(f"**Type:** {opp_type_label} | {source_badge}")
                st.write(f"**Relevance:** {opp.get('relevance', '?')}/10 | "
                         f"**Intent:** {opp.get('intent', '?')}/10 | "
                         f"**Freshness:** {opp.get('freshness', '?')}/10")
                st.write(f"**Reasoning:** {reasoning}")

                top_comments = opp.get("top_comments", [])
                if top_comments:
                    with st.expander(f"{len(top_comments)} top comment(s) found"):
                        for tc in top_comments:
                            st.markdown(f"> {tc.get('body', '')}")
                            st.caption(f"Score: {tc.get('score', '?')} upvotes")
                            st.markdown("---")

                if url:
                    st.write(f"[Open on Reddit]({url})")

                if allow_strategy:
                    key = f"select_{i}"
                    if key not in st.session_state:
                        st.session_state[key] = default_checked
                    st.checkbox("Include in strategy", key=key)
                else:
                    st.caption("Published — not available for re-selection.")

        if new_opps:
            st.markdown(f"**Found {len(new_opps)} new opportunities:**")
            for i, opp in enumerate(st.session_state.discovery_results):
                if opp.get("url") in new_urls:
                    is_published = opp.get("url") in published_urls
                    render_opportunity(opp, i, allow_strategy=not is_published)

        if old_opps:
            st.markdown("---")
            st.markdown("**Old Opportunities**")
            for i, opp in enumerate(st.session_state.discovery_results):
                if opp.get("url") not in new_urls:
                    is_published = opp.get("url") in published_urls
                    render_opportunity(opp, i, allow_strategy=not is_published, default_checked=False)

        if not new_opps and not old_opps:
            st.info("No opportunities found. Try a different time range or check your brief.")

    elif run_discovery_btn:
        st.info("No opportunities found. Try different search queries or check your brief.")


# ═══════════════════════════════════════════════════════════════════════
# TAB 3: Strategy & Content
# ═══════════════════════════════════════════════════════════════════════

with tab3:
    st.subheader("Strategy & Content Generation")

    if not st.session_state.discovery_results:
        st.info("Run Discovery first to find opportunities.")
    else:
        # Collect selected opportunities
        selected = []
        for i, opp in enumerate(st.session_state.discovery_results):
            if st.session_state.get(f"select_{i}", True):
                selected.append(opp)

        st.write(f"**{len(selected)} opportunities selected** for strategy planning.")

        # Step 1: Strategy
        if st.button("Generate Strategy", type="primary"):
            if not api_key:
                st.error("Set your LLM API key in the sidebar.")
            else:
                with st.spinner("Planning engagement strategy..."):
                    try:
                        llm = get_llm(provider, model_name, api_key)
                        new_strategies = plan_strategy(llm, st.session_state.brief, selected)
                        
                        # ALL newly generated strategies are "new" for drafting — including re-selected old ones
                        new_urls_generated = {s.get("url") for s in new_strategies}
                        st.session_state.new_strategy_urls = new_urls_generated

                        # Replace any existing strategy for the same URL, then prepend brand-new ones
                        existing_strats = [
                            s for s in st.session_state.strategy_results
                            if s.get("url") not in new_urls_generated
                        ]
                        st.session_state.strategy_results = new_strategies + existing_strats
                        save_current_state()
                    except Exception as e:
                        st.error(f"Strategy failed: {str(e)}")

        if st.session_state.strategy_results:
            st.markdown("---")
            new_strat_urls = st.session_state.new_strategy_urls
            new_strats = [s for s in st.session_state.strategy_results if s.get("url") in new_strat_urls]
            old_strats = [s for s in st.session_state.strategy_results if s.get("url") not in new_strat_urls]

            def render_strategy(strat):
                angle = strat.get("angle", "unknown")
                sub = strat.get("subreddit", "unknown")
                approach = strat.get("approach", "")
                content_type = strat.get("content_type", "reply")
                caution = strat.get("caution", "")
                angle_emoji = {
                    "helpful_tip": "", "direct_answer": "", "personal_experience": "",
                    "resource_share": "", "discussion_starter": "",
                }.get(angle, "")
                clean_sub = sub.lstrip("r/") if sub.startswith("r/") else sub
                strat_title = strat.get("title", "") or ""
                expander_label = f"{angle_emoji} r/{clean_sub} — {strat_title}" if strat_title else f"{angle_emoji} r/{clean_sub} — {angle} ({content_type})"
                with st.expander(expander_label):
                    st.write(f"**Approach:** {approach}")
                    key_points = strat.get("key_points", [])
                    if key_points:
                        st.write("**Key Points:**")
                        for pt in key_points:
                            st.write(f"  • {pt}")
                    if caution:
                        st.warning(f"{caution}")

            if new_strats:
                st.markdown(f"**Strategies for {len(new_strats)} opportunities:**")
                for strat in new_strats:
                    render_strategy(strat)
            if old_strats:
                st.markdown("---")
                st.markdown("**Old Strategies**")
                for strat in old_strats:
                    render_strategy(strat)

            # Step 2: Generate content drafts
            st.markdown("---")
            if st.button(" Generate Drafts", type="primary"):
                if not api_key:
                    st.error("Set your LLM API key in the sidebar.")
                else:
                    # Only draft for NEW strategies — old ones already have drafts
                    new_strat_urls_set = st.session_state.new_strategy_urls
                    strats_to_draft = [
                        s for s in st.session_state.strategy_results
                        if s.get("url") in new_strat_urls_set
                    ]

                    # Fallback: if new_strategy_urls is empty (e.g., old project loaded before
                    # persistence was added), draft all strategies without an existing draft
                    if not strats_to_draft:
                        existing_draft_keys = {
                            (d.get("opportunity", {}).get("url"), d.get("subreddit"))
                            for d in st.session_state.drafts
                            if not d.get("rejected", False)
                        }
                        strats_to_draft = [
                            s for s in st.session_state.strategy_results
                            if (s.get("url"), s.get("subreddit")) not in existing_draft_keys
                        ]

                    if not strats_to_draft:
                        st.warning("No new strategies to draft. Generate new strategies first.")
                    else:
                        drafts = []
                        llm = get_llm(provider, model_name, api_key)

                        progress = st.progress(0)
                        status = st.empty()

                        for i, strat in enumerate(strats_to_draft):
                            status.text(f"Drafting {i+1}/{len(strats_to_draft)}: "
                                        f"r/{strat.get('subreddit', '?')}...")
                            try:
                                draft = generate_draft(llm, st.session_state.brief, strat)
                                drafts.append(draft)
                            except Exception as e:
                                st.warning(f"Failed to draft for r/{strat.get('subreddit')}: {e}")

                            progress.progress((i + 1) / len(strats_to_draft))

                        # Merge: new drafts on top, keep old ones below
                        # If we just generated a new draft for an old URL, replace the old draft
                        new_draft_keys = {
                            (d.get("opportunity", {}).get("url"), d.get("subreddit"))
                            for d in drafts
                        }
                        existing_drafts = [
                            d for d in st.session_state.drafts
                            if (d.get("opportunity", {}).get("url"), d.get("subreddit")) not in new_draft_keys
                        ]
                        
                        st.session_state.new_draft_urls = {d.get("opportunity", {}).get("url") for d in drafts}
                        st.session_state.drafts = drafts + existing_drafts
                        save_current_state()
                        status.text(f"Generated {len(drafts)} new drafts!")

        # Show drafts for editing
        if st.session_state.drafts:
            st.markdown("---")
            st.subheader("Draft Review")

            new_draft_urls = st.session_state.new_draft_urls
            drafts_to_remove = []  # collect indices of rejected drafts to delete

            for i, draft in enumerate(st.session_state.drafts):
                if draft.get("rejected", False):
                    continue  # skip already-rejected

                is_new_draft = draft.get("opportunity", {}).get("url") in new_draft_urls
                draft_type = draft.get("draft_type", "reply")
                raw_sub = draft.get("subreddit", "unknown")
                clean_sub = raw_sub.lstrip("r/") if raw_sub.startswith("r/") else raw_sub
                type_emoji = "" if draft_type == "post" else ""
                approved_key = f"approved_{i}"
                edit_key = f"editing_{i}"
                is_approved = st.session_state.get(approved_key, False) or draft.get("approved", False)

                # Section headers
                if i == 0 and is_new_draft:
                    pass  # will be under main header
                elif not is_new_draft and (i == 0 or (i > 0 and st.session_state.drafts[i-1].get("opportunity", {}).get("url") in new_draft_urls)):
                    st.markdown("---")
                    st.markdown("**Old Drafts**")

                raw_body = draft.get("body", "")
                if isinstance(raw_body, str) and raw_body.strip().startswith("{"):
                    try:
                        import json as _json
                        parsed = _json.loads(raw_body)
                        raw_body = parsed.get("body", raw_body)
                    except Exception:
                        pass

                draft_title = draft.get("title", "Draft")
                published_badge = " Published" if draft.get("published", False) else ""
                expander_label = f"{type_emoji} r/{clean_sub} — {draft_title[:70]}{published_badge}"

                with st.expander(expander_label, expanded=not is_approved):
                    if draft_type == "post":
                        st.markdown(f"**Title:** {draft_title}")
                        st.markdown("---")
                    st.markdown(raw_body)

                    st.markdown("")

                    if is_approved:
                        # Approved: just show status, no other buttons
                        st.success("Approved — move to Publish tab.")
                    else:
                        col1, col2, col3 = st.columns(3)

                        with col1:
                            if st.button("Approve", key=f"approve_btn_{i}", type="primary"):
                                st.session_state[approved_key] = True
                                st.session_state.drafts[i]["approved"] = True
                                save_current_state()
                                st.rerun()

                        with col2:
                            is_editing = st.session_state.get(edit_key, False)
                            edit_label = "Done Editing" if is_editing else "Edit"
                            if st.button(edit_label, key=f"edit_btn_{i}"):
                                st.session_state[edit_key] = not is_editing
                                st.rerun()
                            if is_editing:
                                new_body = st.text_area("Content", value=raw_body, height=250, key=f"draft_body_{i}")
                                st.session_state.drafts[i]["body"] = new_body
                                if st.button("Save edits", key=f"save_edit_{i}"):
                                    st.session_state[edit_key] = False
                                    save_current_state()
                                    st.rerun()

                        with col3:
                            if st.button("Reject", key=f"reject_btn_{i}"):
                                # Mark rejected and delete strategy for this opportunity
                                draft_url = draft.get("opportunity", {}).get("url", "")
                                st.session_state.drafts[i]["rejected"] = True
                                # Remove matching strategy
                                st.session_state.strategy_results = [
                                    s for s in st.session_state.strategy_results
                                    if s.get("url", "") != draft_url
                                ]
                                save_current_state()
                                st.rerun()


# ═══════════════════════════════════════════════════════════════════════
# TAB 4: Publish
# ═══════════════════════════════════════════════════════════════════════

with tab4:
    st.subheader("Publish Approved Drafts")

    if not st.session_state.drafts:
        st.info("Generate and approve drafts in the Strategy & Content tab first.")
    else:
        # Collect approved drafts
        approved_drafts = []
        for i, draft in enumerate(st.session_state.drafts):
            # Check both session state key AND the persisted draft field (survives page reload)
            is_approved = st.session_state.get(f"approved_{i}", False) or draft.get("approved", False)
            if (
                is_approved
                and not draft.get("rejected", False)
                and not draft.get("published", False)
            ):
                approved_drafts.append((i, draft))

        if not approved_drafts:
            st.warning("No approved drafts yet. Go to Strategy & Content tab and approve some drafts.")
        else:
            st.success(f"**{len(approved_drafts)} drafts ready to publish:**")

            for idx, (i, draft) in enumerate(approved_drafts):
                draft_type = draft.get("draft_type", "reply")
                sub = draft.get("subreddit", "unknown")
                title = draft.get("title", "Draft")
                body = draft.get("body", "")
                opp = draft.get("opportunity", {})
                url = opp.get("url", "")

                with st.expander(f"{'' if draft_type == 'post' else ''} r/{sub} — {title[:60]}", expanded=True):
                    # Show the final content
                    st.markdown("**Final Content:**")
                    if draft_type == "post":
                        st.markdown(f"**Title:** {title}")
                    st.markdown(body)

                    st.markdown("---")

                    # Determine the correct Reddit URL
                    if draft_type == "post":
                        reddit_url = get_submit_url(sub)
                        action_text = "Copy & Open Reddit Submit Page"
                    else:
                        reddit_url = get_reply_url(url) if url else f"https://www.reddit.com/r/{sub}"
                        action_text = "Copy & Open Reddit Thread"

                    col1, col2 = st.columns(2)

                    with col1:
                        publish_key = f"published_{i}"
                        if st.button(f"{action_text}", key=f"pub_btn_{i}", type="primary"):
                            # Copy content and open browser
                            content_to_copy = body
                            if draft_type == "post":
                                content_to_copy = f"Title: {title}\n\n{body}"

                            success = copy_and_open(content_to_copy, reddit_url)

                            if success:
                                # Mark as published and remove from publish tab
                                st.session_state.drafts[i]["published"] = True
                                draft_url = draft.get("opportunity", {}).get("url", "")
                                if draft_url:
                                    st.session_state.published_urls.add(draft_url)
                                st.session_state[publish_key] = True
                                storage.log_published(
                                    st.session_state.project_name, 
                                    reddit_url, 
                                    content_to_copy, 
                                    draft_type, 
                                    sub
                                )
                                save_current_state()
                                st.success("Content copied! Reddit is opening in your browser. Just paste (Cmd+V) and submit.")
                                st.rerun()
                            else:
                                st.warning("Couldn't copy to clipboard. Opening Reddit anyway...")
                                st.link_button("Open Reddit Link", reddit_url)
                                if st.button("Mark as Published (Manual)"):
                                    st.session_state[publish_key] = True
                                    storage.log_published(
                                        st.session_state.project_name, 
                                        reddit_url, 
                                        content_to_copy, 
                                        draft_type, 
                                        sub
                                    )
                                    st.rerun()
                                st.session_state[publish_key] = True

                    with col2:
                        st.link_button("Open Reddit Link", reddit_url)

                    # Status
                    if draft.get("published", False) or st.session_state.get(f"published_{i}", False):
                        st.success("Sent to Reddit!")

    # Published history
    st.markdown("---")
    st.subheader("Status")
    published_count = sum(1 for d in st.session_state.drafts if d.get("published", False))
    total_drafts = len(st.session_state.drafts)
    approved_count = sum(
        1 for i, d in enumerate(st.session_state.drafts)
        if (st.session_state.get(f"approved_{i}", False) or d.get("approved", False))
        and not d.get("rejected", False)
    )

    col1, col2, col3 = st.columns(3)
    col1.metric("Total Drafts", total_drafts)
    col2.metric("Approved", approved_count)
    col3.metric("Published", published_count)
