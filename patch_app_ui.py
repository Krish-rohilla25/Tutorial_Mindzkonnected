import re

with open("reddit_marketing/app.py", "r") as f:
    content = f.read()

# Extract the draft review block
draft_review_pattern = re.compile(
    r'(# Show drafts for editing\s+if st\.session_state\.drafts:\s+st\.markdown\("---"\)\s+st\.subheader\("Draft Review"\).*?# ═══════════════════════════════════════════════════════════════════════\s+# TAB 4: Publish)',
    re.DOTALL
)

match = draft_review_pattern.search(content)
if not match:
    print("Could not find draft review block.")
    exit(1)

draft_review_code = match.group(1)

# We need to wrap it in a function
function_code = """
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

        raw_body = draft.get("body", "")
        if isinstance(raw_body, str) and raw_body.strip().startswith("{"):
            try:
                import json as _json
                parsed = _json.loads(raw_body)
                raw_body = parsed.get("body", raw_body)
            except Exception:
                pass

        draft_title = draft.get("title", "Draft")
        published_badge = " ✓ Published" if draft.get("published", False) else ""
        expander_label = f"{type_emoji} r/{clean_sub} — {draft_title[:60]}{published_badge}"

        with st.expander(expander_label, expanded=not is_approved):
            if draft_type == "post":
                st.markdown(f"**Title:** {draft_title}")
                st.markdown("---")
            st.markdown(raw_body)

            st.markdown("")

            if is_approved:
                st.success("Approved — move to Publish tab.")
            else:
                col1, col2, col3, col4 = st.columns(4)

                with col1:
                    if st.button("Approve", key=f"approve_btn_{safe_url_id}", type="primary"):
                        st.session_state.drafts[i]["approved"] = True
                        save_current_state()
                        st.rerun()

                with col2:
                    is_editing = st.session_state.get(edit_key, False)
                    edit_label = "Done Editing" if is_editing else "Edit"
                    if st.button(edit_label, key=f"edit_btn_{safe_url_id}"):
                        st.session_state[edit_key] = not is_editing
                        st.session_state[f"show_regen_{safe_url_id}"] = False
                        st.rerun()

                with col3:
                    is_regen = st.session_state.get(f"show_regen_{safe_url_id}", False)
                    regen_label = "Cancel Regen" if is_regen else "Regenerate"
                    if st.button(regen_label, key=f"regen_btn_{safe_url_id}"):
                        st.session_state[f"show_regen_{safe_url_id}"] = not is_regen
                        st.session_state[edit_key] = False
                        st.rerun()

                with col4:
                    if st.button("Reject", key=f"reject_btn_{safe_url_id}"):
                        st.session_state.drafts[i]["rejected"] = True
                        draft_url = draft.get("opportunity", {}).get("url", "")
                        st.session_state.strategy_results = [
                            s for s in st.session_state.strategy_results
                            if s.get("url", "") != draft_url
                        ]
                        save_current_state()
                        st.rerun()

                if st.session_state.get(edit_key, False):
                    new_body = st.text_area("Content", value=raw_body, height=250, key=f"draft_body_{safe_url_id}")
                    st.session_state.drafts[i]["body"] = new_body
                    if st.button("Save edits", key=f"save_edit_{safe_url_id}"):
                        st.session_state[edit_key] = False
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
                                st.session_state.drafts[i] = new_draft
                                st.session_state[f"show_regen_{safe_url_id}"] = False
                                save_current_state()
                                st.rerun()
                            except Exception as e:
                                st.error(f"Failed to regenerate: {e}")
"""

# Place the function right before Tab 1
content = content.replace("# ═══════════════════════════════════════════════════════════════════════\n# TAB 1: Brief", 
                          function_code + "\n\n# ═══════════════════════════════════════════════════════════════════════\n# TAB 1: Brief")

# Replace the original draft review block in tab 3 with a call to the function
tab3_call = """
        # Show drafts for editing
        render_draft_review_ui("Draft Review (Posts & Thread Replies)", allowed_types=["post", "reply"])

# ═══════════════════════════════════════════════════════════════════════
# TAB 4: Publish
"""
content = content.replace(draft_review_code, tab3_call)

# Add a call to the function in tab 6
tab6_end_pattern = re.compile(
    r'(st\.success\("Comment reply drafts are ready in Strategy & Content for approval\."\)\s+)(# ═══════════════════════════════════════════════════════════════════════\s+# TAB 7: Monitor Replies)',
    re.DOTALL
)

tab6_call = """st.success("Comment reply drafts generated successfully!")

        render_draft_review_ui("Comment Reply Drafts", allowed_types=["comment_reply"])

"""

content = re.sub(
    r'st\.success\("Comment reply drafts are ready in Strategy & Content for approval\."\)\s+# ═══════════════════════════════════════════════════════════════════════\s+# TAB 7: Monitor Replies',
    tab6_call + "# ═══════════════════════════════════════════════════════════════════════\n# TAB 7: Monitor Replies",
    content
)

with open("reddit_marketing/app.py", "w") as f:
    f.write(content)
