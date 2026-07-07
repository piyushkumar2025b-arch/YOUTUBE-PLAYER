"""
channel_info.py
───────────────
TubePlay feature module: Channel Profile Viewer

Provides helpers + a Streamlit UI component that:
  • Displays channel avatar, name, subscriber count, video count
  • Lists the 8 most-recent uploads for the channel
  • Allows one-click play / queue for any recent upload

Usage in app.py:
    from channel_info import render_channel_panel
    render_channel_panel(channel_id_or_handle, api_key)
"""

import streamlit as st
import requests


# ── Internal helpers ─────────────────────────────────────────────────────────

def _get_channel_by_id(channel_id: str, api_key: str) -> dict | None:
    """Fetch snippet + statistics for a channel by its ID."""
    url = "https://www.googleapis.com/youtube/v3/channels"
    params = {
        "part": "snippet,statistics,contentDetails",
        "id": channel_id,
        "key": api_key,
    }
    try:
        r = requests.get(url, params=params, timeout=8)
        if r.status_code == 200:
            items = r.json().get("items", [])
            return items[0] if items else None
    except Exception:
        pass
    return None


def _get_channel_by_handle(handle: str, api_key: str) -> dict | None:
    """Fetch channel info by a @handle or forUsername."""
    handle = handle.lstrip("@")
    url = "https://www.googleapis.com/youtube/v3/channels"
    # Try forHandle first (newer API), fall back to forUsername
    for param_key in ("forHandle", "forUsername"):
        params = {
            "part": "snippet,statistics,contentDetails",
            param_key: handle,
            "key": api_key,
        }
        try:
            r = requests.get(url, params=params, timeout=8)
            if r.status_code == 200:
                items = r.json().get("items", [])
                if items:
                    return items[0]
        except Exception:
            pass
    return None


def get_channel_info(channel_id_or_handle: str, api_key: str) -> dict | None:
    """
    Returns a channel data dict or None.
    Accepts: channel ID (UCxxxxxxx), @handle, or plain username.
    """
    value = (channel_id_or_handle or "").strip()
    if not value:
        return None
    if value.startswith("UC") and len(value) == 24:
        return _get_channel_by_id(value, api_key)
    return _get_channel_by_handle(value, api_key)


def get_recent_uploads(uploads_playlist_id: str, api_key: str, max_results: int = 8) -> list[dict]:
    """Fetch the most-recent videos from a channel's uploads playlist."""
    url = "https://www.googleapis.com/youtube/v3/playlistItems"
    params = {
        "part": "snippet",
        "playlistId": uploads_playlist_id,
        "maxResults": max_results,
        "key": api_key,
    }
    try:
        r = requests.get(url, params=params, timeout=8)
        if r.status_code == 200:
            return r.json().get("items", [])
    except Exception:
        pass
    return []


def _fmt_number(n: int | str) -> str:
    n = int(n)
    if n >= 1_000_000_000:
        return f"{n / 1_000_000_000:.1f}B"
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.0f}K"
    return str(n)


# ── Streamlit UI component ────────────────────────────────────────────────────

def render_channel_panel(channel_input: str, api_key: str):
    """
    Render the full channel profile panel inside an already-open Streamlit
    container (expander, tab, etc.).

    Imports play_video / add_unique_to_queue from session_state helpers
    rather than importing app.py (avoids circular imports).
    """
    if not api_key:
        st.caption("Add your YouTube API key in the sidebar to look up channels.")
        return

    # Session cache so we don't re-fetch on every rerun
    cache_key = f"_ch_cache_{channel_input}"
    if cache_key not in st.session_state:
        with st.spinner("Loading channel info…"):
            st.session_state[cache_key] = get_channel_info(channel_input, api_key)

    data = st.session_state.get(cache_key)
    if not data:
        st.warning("Channel not found. Try a channel ID (UCxxxxxxx) or @handle.")
        return

    snip  = data.get("snippet", {})
    stats = data.get("statistics", {})
    content_details = data.get("contentDetails", {})
    uploads_pl_id = content_details.get("relatedPlaylists", {}).get("uploads", "")

    # ── Channel header ────────────────────────────────────────────────────────
    avatar_url = (
        snip.get("thumbnails", {}).get("medium", {}).get("url")
        or snip.get("thumbnails", {}).get("default", {}).get("url", "")
    )
    channel_name = snip.get("title", "Unknown Channel")
    description  = snip.get("description", "")[:300]
    country      = snip.get("country", "")
    subs         = stats.get("subscriberCount", "0")
    video_count  = stats.get("videoCount", "0")
    view_count   = stats.get("viewCount", "0")

    left, right = st.columns([1, 3])
    with left:
        if avatar_url:
            st.image(avatar_url, width=100)
    with right:
        st.markdown(f"### {channel_name}")
        if country:
            st.caption(f"🌍 {country}")
        col_s, col_v, col_vw = st.columns(3)
        with col_s:
            st.metric("Subscribers", _fmt_number(subs))
        with col_v:
            st.metric("Videos", _fmt_number(video_count))
        with col_vw:
            st.metric("Total views", _fmt_number(view_count))
        if description:
            with st.expander("About"):
                st.write(description)

    st.divider()

    # ── Recent uploads ────────────────────────────────────────────────────────
    if not uploads_pl_id:
        st.caption("No uploads playlist found for this channel.")
        return

    uploads_cache_key = f"_ch_uploads_{uploads_pl_id}"
    if uploads_cache_key not in st.session_state:
        with st.spinner("Fetching recent uploads…"):
            st.session_state[uploads_cache_key] = get_recent_uploads(uploads_pl_id, api_key)

    uploads = st.session_state.get(uploads_cache_key, [])
    if not uploads:
        st.caption("No recent uploads found.")
        return

    st.markdown("##### 📹 Recent Uploads")
    cols = st.columns(4)
    for i, item in enumerate(uploads):
        snip_u = item.get("snippet", {})
        resource = snip_u.get("resourceId", {})
        vid_id = resource.get("videoId", "")
        title  = snip_u.get("title", "Untitled")
        thumb  = (
            snip_u.get("thumbnails", {}).get("medium", {}).get("url")
            or snip_u.get("thumbnails", {}).get("default", {}).get("url", "")
        )
        if not vid_id:
            continue
        with cols[i % 4]:
            if thumb:
                st.image(thumb, use_container_width=True)
            short = title[:24] + "…" if len(title) > 24 else title
            st.caption(short)
            c1, c2 = st.columns(2)
            with c1:
                if st.button("▶ Play", key=f"ch_play_{vid_id}", use_container_width=True):
                    # Update session state directly (same pattern as app.py play_video)
                    st.session_state.playing_id    = vid_id
                    st.session_state.playing_title = title
                    st.session_state.scroll_to_player = True
                    st.session_state.watch_count   = st.session_state.get("watch_count", 0) + 1
                    history = st.session_state.get("history", [])
                    if vid_id not in [h[0] for h in history]:
                        history.insert(0, (vid_id, title))
                        st.session_state.history = history[:20]
                    st.rerun()
            with c2:
                if st.button("+ Queue", key=f"ch_queue_{vid_id}", use_container_width=True):
                    queue = st.session_state.get("queue", [])
                    if vid_id not in [q[0] for q in queue]:
                        queue.append((vid_id, title))
                        st.session_state.queue = queue
                    st.rerun()
