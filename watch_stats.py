"""
watch_stats.py
──────────────
TubePlay feature module: Session Analytics Dashboard

Tracks and displays in-session watch stats:
  • Videos watched this session (count, titles)
  • Estimated total watch time (based on average video length)
  • Top channels watched
  • Watch time distribution chart (bar chart via Streamlit)
  • Session start time & duration

Usage in app.py:
    from watch_stats import record_watch_event, render_stats_dashboard
    # Call record_watch_event(video_id, title, channel_name, duration_seconds)
    # whenever a video starts playing (inside play_video flow).
    # Render dashboard inside an expander or tab:
    render_stats_dashboard()
"""

import streamlit as st
import time
from collections import Counter
from datetime import datetime


# ── Session state schema ──────────────────────────────────────────────────────

STATS_DEFAULTS = {
    "_ws_session_start": None,   # float: time.time() when first video played
    "_ws_events": [],            # list of dicts: {vid, title, channel, ts, dur}
}


def _init_stats():
    for k, v in STATS_DEFAULTS.items():
        if k not in st.session_state:
            st.session_state[k] = v


# ── Public API ────────────────────────────────────────────────────────────────

def record_watch_event(
    video_id: str,
    title: str,
    channel_name: str = "",
    duration_seconds: int = 0,
):
    """
    Record that a video was played.
    Call this from app.py's play_video() function.
    duration_seconds=0 means unknown; we'll use 300 (5 min) as the average fallback.
    """
    _init_stats()
    now = time.time()
    if st.session_state["_ws_session_start"] is None:
        st.session_state["_ws_session_start"] = now

    events: list = st.session_state["_ws_events"]
    # Avoid duplicate consecutive events (re-run triggers)
    if events and events[-1]["vid"] == video_id:
        return
    events.append(
        {
            "vid":     video_id,
            "title":   title,
            "channel": channel_name or "Unknown",
            "ts":      now,
            "dur":     duration_seconds if duration_seconds > 0 else 300,
        }
    )
    st.session_state["_ws_events"] = events


def render_stats_dashboard():
    """
    Render the full analytics dashboard.  Call inside an expander or tab.
    """
    _init_stats()
    events: list[dict] = st.session_state.get("_ws_events", [])
    session_start = st.session_state.get("_ws_session_start")

    if not events:
        st.info("No watch events recorded yet.  Play a video to start tracking.")
        return

    # ── Compute metrics ───────────────────────────────────────────────────────
    total_videos    = len(events)
    total_dur_sec   = sum(e["dur"] for e in events)
    total_dur_min   = total_dur_sec / 60
    session_dur_sec = time.time() - session_start if session_start else 0
    session_dur_min = session_dur_sec / 60

    channel_counter = Counter(e["channel"] for e in events)
    top_channels    = channel_counter.most_common(5)

    # ── Metrics row ───────────────────────────────────────────────────────────
    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.metric("Videos Watched", total_videos)
    with m2:
        if total_dur_min >= 60:
            st.metric("Est. Watch Time", f"{total_dur_min / 60:.1f} hrs")
        else:
            st.metric("Est. Watch Time", f"{total_dur_min:.0f} min")
    with m3:
        if session_dur_min >= 60:
            st.metric("Session Duration", f"{session_dur_min / 60:.1f} hrs")
        else:
            st.metric("Session Duration", f"{session_dur_min:.0f} min")
    with m4:
        if session_dur_sec > 0:
            efficiency = (total_dur_sec / session_dur_sec) * 100
            st.metric("Watch Efficiency", f"{min(efficiency, 100):.0f}%")
        else:
            st.metric("Watch Efficiency", "—")

    st.divider()

    # ── Top channels bar chart ────────────────────────────────────────────────
    if top_channels:
        st.markdown("##### 📺 Top Channels This Session")
        ch_names   = [ch for ch, _ in top_channels]
        ch_counts  = [cnt for _, cnt in top_channels]
        # Simple horizontal bar using st.progress + markdown
        max_cnt = max(ch_counts) or 1
        for name, cnt in zip(ch_names, ch_counts):
            pct = int(cnt / max_cnt * 100)
            short_name = name[:30] + "…" if len(name) > 30 else name
            st.markdown(
                f"<div style='margin-bottom:4px'>"
                f"<span style='font-size:13px'>{short_name}</span>"
                f"<span style='float:right;font-size:11px;color:#888'>{cnt} video{'s' if cnt>1 else ''}</span>"
                f"</div>",
                unsafe_allow_html=True,
            )
            st.progress(pct)
        st.markdown("")

    # ── Recent watch timeline ─────────────────────────────────────────────────
    st.markdown("##### 🕒 Watch Timeline")
    for e in reversed(events[-10:]):
        ts_str = datetime.fromtimestamp(e["ts"]).strftime("%H:%M:%S")
        dur_str = (
            f"{e['dur'] // 60}m {e['dur'] % 60:02d}s"
            if e["dur"] < 3600
            else f"{e['dur'] // 3600}h {(e['dur'] % 3600) // 60}m"
        )
        title_short = e["title"][:45] + "…" if len(e["title"]) > 45 else e["title"]
        col_time, col_title, col_ch, col_dur, col_play = st.columns([1, 4, 2, 1, 1])
        with col_time:
            st.caption(ts_str)
        with col_title:
            st.markdown(
                f"<span style='font-size:13px'>{title_short}</span>",
                unsafe_allow_html=True,
            )
        with col_ch:
            st.caption(e["channel"][:20])
        with col_dur:
            st.caption(f"~{dur_str}")
        with col_play:
            if st.button("▶", key=f"ws_replay_{e['vid']}_{e['ts']}", help="Replay"):
                st.session_state.playing_id    = e["vid"]
                st.session_state.playing_title = e["title"]
                st.session_state.scroll_to_player = True
                st.rerun()

    # ── Reset ─────────────────────────────────────────────────────────────────
    st.divider()
    if st.button("🗑 Clear session stats", use_container_width=True):
        st.session_state["_ws_events"]        = []
        st.session_state["_ws_session_start"] = None
        st.rerun()
