"""
video_comments.py
─────────────────
TubePlay feature module: Video Comments Viewer

Provides helpers + a Streamlit UI component that:
  • Fetches and displays top-level comments for any video (sorted by top/new)
  • Shows author avatar, author name, like count, publish date
  • Supports searching/filtering through loaded comments
  • "Load more" pagination support

Usage in app.py (inside the playing-video section):
    from video_comments import render_comments_panel
    render_comments_panel(video_id, api_key)

Requirements: YouTube Data API v3 key with commentThreads.list scope.
"""

import streamlit as st
import requests
from datetime import datetime, timezone


# ── Internal helpers ─────────────────────────────────────────────────────────

def fetch_comments(
    video_id: str,
    api_key: str,
    max_results: int = 20,
    order: str = "relevance",
    page_token: str | None = None,
) -> tuple[list[dict], str | None, str | None]:
    """
    Fetch a page of top-level comments for *video_id*.

    Returns:
        (comments_list, next_page_token, error_message)
        comments_list entries have keys:
            author_name, author_avatar, text, like_count, published_at, comment_id
    """
    url = "https://www.googleapis.com/youtube/v3/commentThreads"
    params = {
        "part": "snippet",
        "videoId": video_id,
        "maxResults": min(max_results, 100),
        "order": order,
        "key": api_key,
    }
    if page_token:
        params["pageToken"] = page_token

    try:
        r = requests.get(url, params=params, timeout=10)
    except Exception as exc:
        return [], None, f"Request failed: {exc}"

    if r.status_code == 403:
        data = r.json()
        reason = data.get("error", {}).get("errors", [{}])[0].get("reason", "")
        if reason == "commentsDisabled":
            return [], None, "Comments are disabled for this video."
        return [], None, "API quota exceeded or comments access denied."
    if r.status_code != 200:
        return [], None, f"API error {r.status_code}"

    data = r.json()
    next_token = data.get("nextPageToken")
    comments = []
    for item in data.get("items", []):
        top = item.get("snippet", {}).get("topLevelComment", {}).get("snippet", {})
        comments.append(
            {
                "comment_id":    item.get("id", ""),
                "author_name":   top.get("authorDisplayName", "Unknown"),
                "author_avatar": top.get("authorProfileImageUrl", ""),
                "text":          top.get("textDisplay", ""),
                "like_count":    int(top.get("likeCount", 0)),
                "published_at":  top.get("publishedAt", ""),
            }
        )
    return comments, next_token, None


def _pretty_date(iso: str) -> str:
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        delta = now - dt
        days = delta.days
        if days == 0:
            return "today"
        if days == 1:
            return "yesterday"
        if days < 7:
            return f"{days} days ago"
        if days < 30:
            return f"{days // 7} weeks ago"
        if days < 365:
            return f"{days // 30} months ago"
        return f"{days // 365} years ago"
    except Exception:
        return iso[:10] if iso else ""


# ── Streamlit UI component ────────────────────────────────────────────────────

def render_comments_panel(video_id: str, api_key: str):
    """
    Render a comment viewer panel. Call inside an expander or tab.

    Session-state keys used (all scoped to this video):
        _cmt_list_{video_id}      – cached list of comment dicts
        _cmt_next_{video_id}      – next page token
        _cmt_order_{video_id}     – "relevance" | "time"
        _cmt_loaded_{video_id}    – bool, whether first fetch was done
    """
    if not api_key:
        st.caption("Add your YouTube API key to view comments.")
        return

    order_key  = f"_cmt_order_{video_id}"
    list_key   = f"_cmt_list_{video_id}"
    next_key   = f"_cmt_next_{video_id}"
    loaded_key = f"_cmt_loaded_{video_id}"

    if order_key not in st.session_state:
        st.session_state[order_key] = "relevance"

    # ── Controls row ─────────────────────────────────────────────────────────
    cc1, cc2, cc3 = st.columns([2, 2, 2])
    with cc1:
        new_order = st.selectbox(
            "Sort comments",
            ["relevance", "time"],
            index=["relevance", "time"].index(st.session_state[order_key]),
            key=f"cmt_order_sel_{video_id}",
            label_visibility="collapsed",
        )
        if new_order != st.session_state[order_key]:
            st.session_state[order_key] = new_order
            # Reset when order changes
            st.session_state.pop(list_key, None)
            st.session_state.pop(next_key, None)
            st.session_state[loaded_key] = False

    with cc2:
        search_q = st.text_input(
            "Search comments",
            placeholder="Filter comments…",
            key=f"cmt_search_{video_id}",
            label_visibility="collapsed",
        )

    with cc3:
        if st.button("Load comments", key=f"cmt_load_{video_id}", use_container_width=True):
            with st.spinner("Fetching comments…"):
                comments, next_tok, err = fetch_comments(
                    video_id, api_key, order=st.session_state[order_key]
                )
            if err:
                st.warning(err)
            else:
                st.session_state[list_key]   = comments
                st.session_state[next_key]   = next_tok
                st.session_state[loaded_key] = True

    # ── Comment list ─────────────────────────────────────────────────────────
    if not st.session_state.get(loaded_key):
        st.caption("Click **Load comments** to fetch the top comments for this video.")
        return

    all_comments: list[dict] = st.session_state.get(list_key, [])
    if not all_comments:
        st.info("No comments found.")
        return

    # Filter
    display = all_comments
    if search_q:
        q_lower = search_q.lower()
        display = [
            c for c in all_comments
            if q_lower in c["text"].lower() or q_lower in c["author_name"].lower()
        ]

    st.caption(
        f"Showing {len(display)} of {len(all_comments)} loaded comment(s) "
        f"• sorted by **{st.session_state[order_key]}**"
    )

    # Render each comment
    for c in display:
        with st.container():
            a_col, t_col = st.columns([1, 9])
            with a_col:
                if c["author_avatar"]:
                    st.image(c["author_avatar"], width=36)
                else:
                    st.markdown("👤")
            with t_col:
                date_str = _pretty_date(c["published_at"])
                st.markdown(
                    f"<span style='font-weight:700;font-size:13px'>{c['author_name']}</span>"
                    f"<span style='color:#888;font-size:11px;margin-left:8px'>{date_str}</span>",
                    unsafe_allow_html=True,
                )
                # YouTube uses <br> in textDisplay; strip basic HTML tags for safety
                clean_text = (
                    c["text"]
                    .replace("<br>", "\n")
                    .replace("<br/>", "\n")
                    .replace("&amp;", "&")
                    .replace("&lt;", "<")
                    .replace("&gt;", ">")
                    .replace("&#39;", "'")
                    .replace("&quot;", '"')
                )
                st.write(clean_text)
                st.caption(f"👍 {c['like_count']:,}")
            st.divider()

    # ── Load more ────────────────────────────────────────────────────────────
    next_token = st.session_state.get(next_key)
    if next_token:
        if st.button("Load more comments", key=f"cmt_more_{video_id}", use_container_width=True):
            with st.spinner("Loading more…"):
                more, new_next, err = fetch_comments(
                    video_id, api_key,
                    order=st.session_state[order_key],
                    page_token=next_token,
                )
            if err:
                st.warning(err)
            else:
                st.session_state[list_key] = all_comments + more
                st.session_state[next_key] = new_next
                st.rerun()
