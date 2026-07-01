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
from reddit_marketing.agents.discovery import (
    run_discovery,
    run_subreddit_discovery,
    score_comment_opportunities,
)
from reddit_marketing.agents.strategy import plan_strategy
from reddit_marketing.agents.content import generate_comment_reply_draft, generate_draft
from reddit_marketing.publisher import copy_and_open, get_submit_url, get_reply_url
from reddit_marketing.reddit_search import fetch_thread_comments_rss
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
        st.session_state.subreddit_results = []
        st.session_state.search_queries = []
        st.session_state.strategy_results = []
        st.session_state.drafts = []
        storage.save_project(new_project_name, st.session_state.brief.__dict__, {
            "search_queries": [],
            "discovery_results": [],
            "subreddit_results": [],
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
            st.session_state.subreddit_results = state_dict.get("subreddit_results", [])
            st.session_state.strategy_results = state_dict.get("strategy_results", [])
            st.session_state.drafts = state_dict.get("drafts", [])
            # Restore URL sets (stored as lists in DB)
            st.session_state.new_opportunity_urls = set(state_dict.get("new_opportunity_urls", []))
            st.session_state.new_subreddit_urls = set(state_dict.get("new_subreddit_urls", []))
            st.session_state.new_strategy_urls = set(state_dict.get("new_strategy_urls", []))
            st.session_state.new_draft_urls = set(state_dict.get("new_draft_urls", []))
            st.session_state.published_urls = set(state_dict.get("published_urls", []))
            st.session_state.monitored_comments = state_dict.get("monitored_comments", [])
            st.session_state.monitor_reply_drafts = state_dict.get("monitor_reply_drafts", {})
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
if "subreddit_results" not in st.session_state:
    st.session_state.subreddit_results = []

if "search_queries" not in st.session_state:
    st.session_state.search_queries = []

if "strategy_results" not in st.session_state:
    st.session_state.strategy_results = []

if "drafts" not in st.session_state:
    st.session_state.drafts = []

# Track which items are "new" (from the latest run) vs "old" (from previous runs)
if "new_opportunity_urls" not in st.session_state:
    st.session_state.new_opportunity_urls = set()
if "new_subreddit_urls" not in st.session_state:
    st.session_state.new_subreddit_urls = set()
if "new_strategy_urls" not in st.session_state:
    st.session_state.new_strategy_urls = set()
if "new_draft_urls" not in st.session_state:
    st.session_state.new_draft_urls = set()
# Track which opportunity URLs have been published
if "published_urls" not in st.session_state:
    st.session_state.published_urls = set()
if "monitored_comments" not in st.session_state:
    st.session_state.monitored_comments = []
if "new_monitored_comment_ids" not in st.session_state:
    st.session_state.new_monitored_comment_ids = set()
if "monitor_reply_drafts" not in st.session_state:
    st.session_state.monitor_reply_drafts = {}

def save_current_state():
    """Helper to dump current state to DB for the active project."""
    state_dict = {
        "search_queries": st.session_state.search_queries,
        "discovery_results": st.session_state.discovery_results,
        "subreddit_results": st.session_state.subreddit_results,
        "strategy_results": st.session_state.strategy_results,
        "drafts": st.session_state.drafts,
        # Store sets as lists (JSON serializable)
        "new_opportunity_urls": list(st.session_state.new_opportunity_urls),
        "new_subreddit_urls": list(st.session_state.new_subreddit_urls),
        "new_strategy_urls": list(st.session_state.new_strategy_urls),
        "new_draft_urls": list(st.session_state.new_draft_urls),
        "published_urls": list(st.session_state.published_urls),
        "monitored_comments": st.session_state.monitored_comments,
        "new_monitored_comment_ids": list(st.session_state.new_monitored_comment_ids),
        "monitor_reply_drafts": st.session_state.monitor_reply_drafts,
    }
    storage.save_project(st.session_state.project_name, st.session_state.brief.__dict__, state_dict)



def render_draft_review_ui(title="Draft Review", allowed_types=None):
    # Filter drafts first to see if any match allowed_types
    if allowed_types is not None:
        relevant_drafts = [d for d in st.session_state.drafts if d.get("draft_type") in allowed_types]
    else:
        relevant_drafts = st.session_state.drafts

    if not relevant_drafts:
        return

    st.markdown("---")
    st.subheader(title)

    new_draft_urls = st.session_state.new_draft_urls

    for i, draft in enumerate(st.session_state.drafts):
        if allowed_types is not None and draft.get("draft_type") not in allowed_types:
            continue
        if draft.get("rejected", False):
            continue  # skip already-rejected

        is_new_draft = draft.get("opportunity", {}).get("url") in new_draft_urls
        draft_type = draft.get("draft_type", "reply")
        raw_sub = draft.get("subreddit", "unknown")
        clean_sub = raw_sub.lstrip("r/") if raw_sub.startswith("r/") else raw_sub
        type_emoji = "" if draft_type == "post" else ""
        url_id = draft.get("opportunity", {}).get("url", str(i))
        # Ensure url_id is safe for Streamlit keys
        import hashlib
        safe_url_id = hashlib.md5(url_id.encode('utf-8')).hexdigest()
        edit_key = f"editing_{safe_url_id}"
        is_approved = draft.get("approved", False)
        draft_version = draft.get("version", 0)

        raw_body = draft.get("body", "")
        if isinstance(raw_body, str) and raw_body.strip().startswith("{"):
            try:
                import json as _json
                parsed = _json.loads(raw_body)
                raw_body = parsed.get("body", raw_body)
            except Exception:
                pass

        if draft_type == "comment_reply":
            comment_body = draft.get("opportunity", {}).get("comment", {}).get("body", "")
            preview = (comment_body[:60] + "...") if len(comment_body) > 60 else comment_body
            draft_title = preview.replace("\n", " ").strip() or "Comment Reply"
        else:
            draft_title = draft.get("title", "Draft")
        published_badge = " ✓ Published" if draft.get("published", False) else ""
        expander_label = f"{type_emoji} r/{clean_sub} — {draft_title[:60]}{published_badge}"

        with st.expander(expander_label, expanded=not is_approved):
            if draft_type == "post":
                st.markdown(f"**Title:** {draft_title}")
                st.markdown("---")
            
            if is_approved:
                st.markdown(raw_body)
                st.success("Approved — move to Publish tab.")
            else:
                new_body = st.text_area("Edit Draft Content:", value=raw_body, height=250, key=f"draft_body_{safe_url_id}_v{draft_version}")
                if new_body != raw_body:
                    st.session_state.drafts[i]["body"] = new_body
                    save_current_state()

                col1, col2, col3 = st.columns(3)

                with col1:
                    if st.button("Approve", key=f"approve_btn_{safe_url_id}", type="primary"):
                        st.session_state.drafts[i]["approved"] = True
                        save_current_state()
                        st.rerun()

                with col2:
                    is_regen = st.session_state.get(f"show_regen_{safe_url_id}", False)
                    regen_label = "Cancel Regen" if is_regen else "Regenerate"
                    if st.button(regen_label, key=f"regen_btn_{safe_url_id}"):
                        st.session_state[f"show_regen_{safe_url_id}"] = not is_regen
                        st.rerun()

                with col3:
                    if st.button("Reject", key=f"reject_btn_{safe_url_id}"):
                        st.session_state.drafts[i]["rejected"] = True
                        draft_url = draft.get("opportunity", {}).get("url", "")
                        st.session_state.strategy_results = [
                            s for s in st.session_state.strategy_results
                            if s.get("url", "") != draft_url
                        ]
                        save_current_state()
                        st.rerun()

                if st.session_state.get(f"show_regen_{safe_url_id}", False):
                    suggestion = st.text_area("How should we improve this draft?", placeholder="e.g. Make it shorter...", key=f"regen_input_{safe_url_id}")
                    if st.button("Generate New Draft", key=f"do_regen_{safe_url_id}"):
                        with st.spinner("Regenerating draft based on feedback..."):
                            from reddit_marketing.agents.content import generate_draft
                            try:
                                llm = get_llm(provider, model_name, api_key)
                                new_draft = generate_draft(llm, st.session_state.brief, draft.get("opportunity"), feedback=suggestion)
                                new_draft["version"] = draft_version + 1
                                st.session_state.drafts[i] = new_draft
                                st.session_state[f"show_regen_{safe_url_id}"] = False
                                
                                if f"regen_input_{safe_url_id}" in st.session_state:
                                    del st.session_state[f"regen_input_{safe_url_id}"]
                                    
                                save_current_state()
                                st.rerun()
                            except Exception as e:
                                st.error(f"Failed to regenerate: {e}")


# ── Tabs ─────────────────────────────────────────────────────────────────

tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "Project Brief",
    "Discovery",
    "Strategy & Content",
    "Publish",
    "History",
    "Monitor Posts"
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

    st.markdown("---")
    st.info(" **Next Step:** Go to the **Discovery** tab at the top to find subreddits and threads.")


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
    st.subheader("Discovery")
    st.write("Generate search queries from the brief, then choose whether to find subreddits for original posts or threads to reply to.")

    st.markdown("### 1. Search Queries")
    if st.button("Generate Search Queries"):
        if not api_key:
            st.error("Please set the LLM API key in the sidebar.")
        else:
            with st.spinner("Generating..."):
                try:
                    from reddit_marketing.agents.discovery import generate_search_queries
                    llm = get_llm(provider, model_name, api_key)
                    st.session_state.search_queries = generate_search_queries(llm, st.session_state.brief)
                    save_current_state()
                except Exception as e:
                    st.error(f"Failed to generate queries: {e}")

    current_queries = "\n".join(st.session_state.get("search_queries", []))
    edited_queries_text = st.text_area(
        "Search Queries (one per line)",
        value=current_queries,
        height=150,
        placeholder="AI-powered workout apps\nbest fitness tracker 2024",
    )

    st.markdown("---")
    st.markdown("### 2. Choose Discovery Mode")
    discovery_mode = st.radio(
        "What do you want to find?",
        ["Find subreddits to post in", "Find threads to reply to"],
        horizontal=True,
    )

    with st.expander(" Advanced Search Settings"):
        col_opts1, col_opts2, col_opts3, col_opts4 = st.columns(4)
        with col_opts1:
            time_range = st.selectbox(
                "Time Range",
                options=["day", "week", "month", "year", "all"],
                index=2,
                format_func=lambda x: "Past 24 hours" if x == "day" else f"Past {x}" if x != "all" else "Any time",
            )
        with col_opts2:
            max_total = st.slider("Max total results", min_value=1, max_value=30, value=10)
        with col_opts3:
            max_per_query = st.slider("Max per query", min_value=1, max_value=20, value=5)
        with col_opts4:
            search_method = st.selectbox(
                "Search Source",
                options=["reddit_json", "tavily"],
                index=0,
                format_func=lambda x: {
                    "reddit_json": "Reddit JSON",
                    "tavily": "Tavily",
                }[x],
            )

    rss_subreddits = []

    tr_param = None if time_range == "all" else time_range
    run_label = "Find Subreddits" if discovery_mode.startswith("Find subreddits") else "Find Reply Opportunities"
    run_discovery_btn = st.button(run_label, type="primary")

    if run_discovery_btn:
        final_queries = [q.strip() for q in edited_queries_text.split("\n") if q.strip()]
        if not final_queries:
            st.error("Please provide at least one search query.")
        elif not api_key:
            st.error("Please set the LLM API key in the sidebar.")
        elif search_method == "tavily" and not tavily_key:
            st.error("Please set the Tavily API key in the sidebar or switch to Reddit JSON/RSS.")
        elif search_method == "rss" and not rss_subreddits:
            st.error("Please provide at least one subreddit for RSS scanning.")
        else:
            st.session_state.search_queries = final_queries
            llm = get_llm(provider, model_name, api_key)
            try:
                if discovery_mode.startswith("Find subreddits"):
                    with st.spinner("Finding subreddits for original posts..."):
                        results = run_subreddit_discovery(
                            llm,
                            tavily_key,
                            st.session_state.brief,
                            final_queries,
                            max_results_per_query=max_per_query,
                            time_range=tr_param,
                            search_method=search_method,
                            rss_subreddits=rss_subreddits,
                            max_subreddits=max_total,
                        )
                    existing_urls = {o.get("url") for o in st.session_state.subreddit_results}
                    fresh = [r for r in results if r.get("url") not in existing_urls]
                    st.session_state.new_subreddit_urls = {r.get("url") for r in fresh}
                    st.session_state.subreddit_results = fresh + st.session_state.subreddit_results
                else:
                    with st.spinner("Finding Reddit threads to reply to..."):
                        results = run_discovery(
                            llm,
                            tavily_key,
                            st.session_state.brief,
                            final_queries,
                            max_results_per_query=max_per_query,
                            time_range=tr_param,
                            search_method=search_method,
                            rss_subreddits=rss_subreddits,
                        )
                    existing_urls = {o.get("url") for o in st.session_state.discovery_results}
                    fresh = [r for r in results[:max_total] if r.get("url") not in existing_urls]
                    st.session_state.new_opportunity_urls = {r.get("url") for r in fresh}
                    st.session_state.discovery_results = fresh + st.session_state.discovery_results
                save_current_state()
            except Exception as e:
                st.error(f"Discovery failed: {e}")

    if st.session_state.search_queries:
        with st.expander(f"Search queries used ({len(st.session_state.search_queries)})"):
            for q in st.session_state.search_queries:
                st.write(f"- {q}")

    st.markdown("---")
    if discovery_mode.startswith("Find subreddits"):
        st.markdown("### Subreddits to Post In")
        if not st.session_state.subreddit_results:
            st.info("No subreddit targets yet.")
        for i, opp in enumerate(st.session_state.subreddit_results):
            url = opp.get("url", "")
            sub = opp.get("subreddit", "unknown")
            score = opp.get("total_score", "?")
            try:
                score_num = float(score)
                score_dot = "🟢" if score_num >= 15 else "🟡" if score_num >= 10 else "🔴"
            except:
                score_dot = "⚪"
            
            is_new = url in st.session_state.new_subreddit_urls
            new_badge = "  NEW" if is_new else ""
            
            key = f"select_subreddit_{i}"
            if key not in st.session_state:
                st.session_state[key] = is_new
                
            col1, col2 = st.columns([0.05, 0.95])
            with col1:
                st.write("") # spacer to align checkbox with expander vertically
                st.checkbox("Select subreddit", key=key, label_visibility="collapsed")
            with col2:
                label = f"{score_dot} [{score}/20] r/{sub} — {opp.get('title', 'Create a post')}{new_badge}"
                with st.expander(label, expanded=is_new):
                    st.write(f"**Reasoning:** {opp.get('reasoning', '')}")
                    if url:
                        st.write(f"[Open subreddit]({url})")
                    if opp.get("evidence"):
                        st.write("**Evidence:**")
                        for item in opp.get("evidence", []):
                            st.write(f"- {item}")
    else:
        st.markdown("### Threads to Reply To")
        if not st.session_state.discovery_results:
            st.info("No reply opportunities yet.")
        for i, opp in enumerate(st.session_state.discovery_results):
            url = opp.get("url", "")
            sub = opp.get("subreddit", "unknown")
            score = opp.get("total_score", "?")
            try:
                score_num = float(score)
                score_dot = "🟢" if score_num >= 15 else "🟡" if score_num >= 10 else "🔴"
            except:
                score_dot = "⚪"
                
            is_new = url in st.session_state.new_opportunity_urls
            new_badge = " ✨ NEW" if is_new else ""
            published_badge = " ✓ Published" if url in st.session_state.published_urls else ""
            
            key = f"select_reply_{i}"
            if key not in st.session_state:
                st.session_state[key] = is_new
                
            col1, col2 = st.columns([0.05, 0.95])
            with col1:
                st.write("") # spacer to align checkbox with expander vertically
                st.checkbox("Select thread", key=key, label_visibility="collapsed", disabled=url in st.session_state.published_urls)
            with col2:
                with st.expander(f"{score_dot} [{score}/20] r/{sub} — {opp.get('title', 'Untitled')}{published_badge}{new_badge}", expanded=is_new):
                    st.write(f"**Relevance:** {opp.get('relevance', '?')}/10 | **Intent:** {opp.get('intent', '?')}/10")
                    st.write(f"**Reasoning:** {opp.get('reasoning', '')}")
                    if url:
                        st.write(f"[Open on Reddit]({url})")
                        
    if st.session_state.discovery_results or st.session_state.subreddit_results:
        st.markdown("---")
        st.info("👉 **Next Step:** After selecting opportunities, go to the **Strategy & Content** tab to generate drafts.")


# ═══════════════════════════════════════════════════════════════════════
# TAB 3: Strategy & Content
# ═══════════════════════════════════════════════════════════════════════

with tab3:
    st.subheader("Strategy & Content Generation")

    if not st.session_state.discovery_results and not st.session_state.subreddit_results:
        st.info("Run Discovery first to find subreddits or reply opportunities.")
    else:
        # Collect selected opportunities
        selected = []
        published_urls = st.session_state.published_urls
        for i, opp in enumerate(st.session_state.subreddit_results):
            is_new = opp.get("url") in st.session_state.new_subreddit_urls
            if st.session_state.get(f"select_subreddit_{i}", is_new):
                selected.append(opp)
        for i, opp in enumerate(st.session_state.discovery_results):
            if opp.get("url") in published_urls:
                continue
            is_new = opp.get("url") in st.session_state.new_opportunity_urls
            if st.session_state.get(f"select_reply_{i}", is_new):
                selected.append(opp)

        post_count = sum(1 for item in selected if item.get("opportunity_type") == "new_post")
        reply_count = len(selected) - post_count
        st.write(f"**{post_count} subreddit posts** and **{reply_count} thread replies** selected for strategy planning.")

        # Step 1: Strategy
        if st.button("Generate Strategy", type="primary"):
            if not api_key:
                st.error("Set your LLM API key in the sidebar.")
            elif not selected:
                st.warning("Select at least one subreddit or thread first.")
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
        render_draft_review_ui("Draft Review (Posts & Thread Replies)", allowed_types=["post", "reply"])
        
        if st.session_state.drafts:
            st.markdown("---")
            st.info("👉 **Next Step:** Once you have approved your drafts, go to the **Publish** tab to post them on Reddit.")

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
            if (
                draft.get("approved", False)
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
                        default_published_url = ""
                    else:
                        reddit_url = get_reply_url(url) if url else f"https://www.reddit.com/r/{sub}"
                        action_text = "Copy & Open Reddit Thread"
                        default_published_url = reddit_url

                    col1, col2 = st.columns(2)
                    url_id = opp.get("url", str(i))

                    with col1:
                        if st.button(f"{action_text}", key=f"pub_btn_{url_id}", type="primary"):
                            # Copy content and open browser
                            content_to_copy = body
                            if draft_type == "post":
                                content_to_copy = f"Title: {title}\n\n{body}"

                            success = copy_and_open(content_to_copy, reddit_url)

                            if success:
                                st.success("Content copied. After submitting on Reddit, paste the final Reddit URL below and mark it published.")
                            else:
                                st.warning("Couldn't copy to clipboard. Opening Reddit anyway...")
                                st.link_button("Open Reddit Link", reddit_url)

                    with col2:
                        st.link_button("Open Reddit Link", reddit_url)

                    published_url = st.text_input(
                        "Final Reddit URL",
                        value=default_published_url,
                        placeholder="Paste the submitted post/comment URL here",
                        key=f"published_url_{url_id}",
                    )
                    if st.button("Mark as Published", key=f"manual_pub_{url_id}"):
                        final_url = published_url.strip() or reddit_url
                        content_to_copy = body
                        if draft_type == "post":
                            content_to_copy = f"Title: {title}\n\n{body}"

                        st.session_state.drafts[i]["published"] = True
                        st.session_state.drafts[i]["published_url"] = final_url
                        draft_url = draft.get("opportunity", {}).get("url", "")
                        if draft_url:
                            st.session_state.published_urls.add(draft_url)
                        if final_url:
                            st.session_state.published_urls.add(final_url)
                        storage.log_published(
                            st.session_state.project_name,
                            final_url,
                            content_to_copy,
                            draft_type,
                            sub,
                        )
                        save_current_state()
                        st.rerun()

                    # Status
                    if draft.get("published", False):
                        st.success("Sent to Reddit!")

    # Published history
    st.markdown("---")
    st.subheader("Status")
    published_count = sum(1 for d in st.session_state.drafts if d.get("published", False))
    total_drafts = len(st.session_state.drafts)
    approved_count = sum(
        1 for d in st.session_state.drafts
        if d.get("approved", False) and not d.get("rejected", False)
    )

    col1, col2, col3 = st.columns(3)
    col1.metric("Total Drafts", total_drafts)
    col2.metric("Approved", approved_count)
    col3.metric("Published", published_count)


# ═══════════════════════════════════════════════════════════════════════
# TAB 6: Monitor
# ═══════════════════════════════════════════════════════════════════════

with tab6:
    st.subheader("Monitor Published Posts")
    st.write("Fetch comments from published Reddit URLs, select useful replies, and draft responses for human review.")

    published_items = storage.get_published_log(st.session_state.project_name)
    monitorable_items = [
        item for item in published_items
        if item.get("url") and "reddit.com" in item.get("url", "") and "/submit" not in item.get("url", "")
    ]

    if not monitorable_items:
        st.info("No monitorable Reddit URLs yet. Publish a draft and paste the final Reddit post/thread URL first.")
    else:
        st.markdown(f"**{len(monitorable_items)} published Reddit URLs available for monitoring.**")

        options = [item.get("url") for item in monitorable_items if item.get("url")]
        selected_urls = st.multiselect("Select URLs to monitor", options, default=options)

        col1, col2 = st.columns(2)
        with col1:
            max_comments = st.slider("Max comments per URL", min_value=5, max_value=100, value=20, step=5)
        with col2:
            sort_map = {"New Comments": "new", "Top Comments": "top", "Best Comments": "confidence"}
            comment_sort_label = st.selectbox("Sort By", options=list(sort_map.keys()))
            comment_sort = sort_map[comment_sort_label]

        if st.button("Fetch Comments", type="primary"):
            if not selected_urls:
                st.warning("Please select at least one URL to monitor.")
            else:
                with st.spinner("Fetching Reddit comments..."):
                    try:
                        all_comments = []
                        selected_items = [item for item in monitorable_items if item.get("url") in selected_urls]
                        for item in selected_items:
                            comments = fetch_thread_comments_rss(item.get("url", ""), limit=max_comments, sort=comment_sort)
                            all_comments.extend(comments)

                        # Clear ALL previous comment opportunities before adding new ones
                        st.session_state.monitored_comments = []

                        llm = get_llm(provider, model_name, api_key)
                        new_opps = score_comment_opportunities(llm, st.session_state.brief, all_comments)
                        st.session_state.new_monitored_comment_ids = {
                            item.get("comment", {}).get("id")
                            for item in new_opps
                        }
                        st.session_state.monitored_comments = new_opps + st.session_state.monitored_comments
                        save_current_state()
                        if new_opps:
                            st.success(f"Found {len(new_opps)} comment(s).")
                        else:
                            st.info("No comments found for the selected URLs.")
                    except Exception as e:
                        st.error(f"Monitoring failed: {e}")

        if st.session_state.monitored_comments:
            st.markdown("---")
            st.subheader("Comment Opportunities")

            selected_comments = []
            for i, opp in enumerate(st.session_state.monitored_comments):
                comment = opp.get("comment", {})

                comment_id = comment.get("id", f"comment_{i}")
                sub = opp.get("subreddit", "unknown")
                score = opp.get("total_score", "?")
                
                comment_body = comment.get("body", "")
                preview = (comment_body[:60] + "...") if len(comment_body) > 60 else comment_body
                preview = preview.replace("\n", " ").strip()
                title_label = preview or "Comment reply"
                
                if opp.get("url") in st.session_state.published_urls:
                    title_label += " ✓ Published"
                
                is_new = comment_id in st.session_state.new_monitored_comment_ids

                with st.expander(f"r/{sub} — {title_label}", expanded=is_new):
                    if comment.get("permalink"):
                        st.write(f"[Open comment]({comment.get('permalink')})")
                    st.markdown("**Comment:**")
                    st.write(comment.get("body", ""))

                    select_key = f"monitor_select_{comment_id}"
                    if select_key not in st.session_state:
                        st.session_state[select_key] = False
                    if st.checkbox("Draft a reply for review", key=select_key):
                        selected_comments.append(opp)

            if st.button("Generate Comment Reply Drafts"):
                if not api_key:
                    st.error("Set your LLM API key in the sidebar.")
                elif not selected_comments:
                    st.warning("Select at least one comment to draft a reply.")
                else:
                    with st.spinner("Drafting comment replies..."):
                        llm = get_llm(provider, model_name, api_key)
                        drafts = []
                        for opp in selected_comments:
                            try:
                                drafts.append(generate_comment_reply_draft(llm, st.session_state.brief, opp))
                            except Exception as e:
                                st.warning(f"Failed to draft reply for {opp.get('url', 'comment')}: {e}")

                        new_draft_keys = {
                            (d.get("opportunity", {}).get("url"), d.get("subreddit"))
                            for d in drafts
                        }
                        existing_drafts = [
                            d for d in st.session_state.drafts
                            if (d.get("opportunity", {}).get("url"), d.get("subreddit")) not in new_draft_keys
                        ]
                        st.session_state.new_draft_urls = {
                            d.get("opportunity", {}).get("url")
                            for d in drafts
                        }
                        st.session_state.drafts = drafts + existing_drafts
                        save_current_state()
                        st.success("Comment reply drafts generated successfully!")

        render_draft_review_ui("Comment Reply Drafts", allowed_types=["comment_reply"])

