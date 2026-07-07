"""
scheduler.py
────────────
TubePlay feature module: Watch Scheduler & Reminders

Lets users schedule a video (or the current queue) to auto-start at a
specific future time, and shows a countdown badge.

How it works (Streamlit limitations note):
  Streamlit can't run background threads reliably across reruns.
  Instead we use a "check on rerun" pattern — the countdown is shown
  and when the user interacts (any rerun) after the trigger time the
  video auto-plays.  Users can keep the app open and periodically
  interact, or use the manual "Check now" button.

Session state keys:
    _sched_events  – list of {vid, title, trigger_ts, label, fired}
    _sched_alarm   – (vid, title) to play immediately on next rerun, or None

Usage in app.py:
    from scheduler import render_scheduler_panel, check_and_fire_scheduled
    # At the top of main content, before the player:
    check_and_fire_scheduled()
    # Inside an expander:
    render_scheduler_panel()
"""

import streamlit as st
import time
from datetime import datetime, date


# ── Defaults ──────────────────────────────────────────────────────────────────

def _init_scheduler():
    if "_sched_events" not in st.session_state:
        st.session_state["_sched_events"] = []
    if "_sched_alarm" not in st.session_state:
        st.session_state["_sched_alarm"] = None


# ── Public: fire check (call every rerun before player) ───────────────────────

def check_and_fire_scheduled() -> bool:
    """
    Check if any scheduled events should fire.
    If yes, sets playing_id/playing_title and returns True.
    Call this near the top of the main content area.
    """
    _init_scheduler()

    # Check if an alarm was set last rerun
    alarm = st.session_state.get("_sched_alarm")
    if alarm:
        vid, title = alarm
        st.session_state["_sched_alarm"] = None
        st.session_state.playing_id    = vid
        st.session_state.playing_title = title
        st.session_state.scroll_to_player = True
        st.session_state.watch_count = st.session_state.get("watch_count", 0) + 1
        history = st.session_state.get("history", [])
        if vid not in [h[0] for h in history]:
            history.insert(0, (vid, title))
            st.session_state.history = history[:20]
        return True

    now = time.time()
    events: list[dict] = st.session_state["_sched_events"]
    fired_any = False
    for evt in events:
        if not evt.get("fired") and evt["trigger_ts"] <= now:
            evt["fired"] = True
            st.session_state["_sched_alarm"] = (evt["vid"], evt["title"])
            fired_any = True
            break  # fire one at a time

    if fired_any:
        st.session_state["_sched_events"] = events
    return fired_any


# ── Internal helpers ──────────────────────────────────────────────────────────

def _format_countdown(trigger_ts: float) -> str:
    remaining = trigger_ts - time.time()
    if remaining <= 0:
        return "Now!"
    h = int(remaining // 3600)
    m = int((remaining % 3600) // 60)
    s = int(remaining % 60)
    if h > 0:
        return f"{h}h {m:02d}m {s:02d}s"
    if m > 0:
        return f"{m}m {s:02d}s"
    return f"{s}s"


# ── Public: UI component ──────────────────────────────────────────────────────

def render_scheduler_panel():
    """
    Render the watch scheduler UI.
    Call inside an expander or tab in app.py.
    """
    _init_scheduler()

    st.markdown("##### ⏰ Schedule a Video to Play")
    st.caption(
        "Pick a video URL/ID and a time. The video will auto-play the next "
        "time you interact with the app after that time."
    )

    with st.form("sched_form", clear_on_submit=True):
        f1, f2 = st.columns([3, 1])
        with f1:
            sched_url = st.text_input(
                "YouTube URL or Video ID",
                placeholder="https://youtu.be/dQw4w9WgXcQ",
                key="sched_url_input",
            )
        with f2:
            sched_label = st.text_input("Label (optional)", placeholder="Morning focus", key="sched_label_input")

        t1, t2, t3 = st.columns(3)
        today = date.today()
        with t1:
            sched_date = st.date_input("Date", value=today, min_value=today, key="sched_date")
        with t2:
            sched_hour = st.number_input("Hour (0-23)", min_value=0, max_value=23,
                                          value=datetime.now().hour, step=1, key="sched_hour")
        with t3:
            sched_min = st.number_input("Minute", min_value=0, max_value=59,
                                         value=0, step=5, key="sched_min")

        # Option: use current queue instead of a single video
        use_current = st.checkbox(
            "Use current playing video instead of URL",
            value=False,
            key="sched_use_current",
        )

        submitted = st.form_submit_button("➕ Add Schedule", use_container_width=True)

    if submitted:
        # Resolve video
        vid_id, title = None, None
        if use_current and st.session_state.get("playing_id"):
            vid_id = st.session_state.playing_id
            title  = st.session_state.playing_title
        elif sched_url:
            # Inline extract (avoid importing app.py)
            import re, urllib.parse
            url_or_id = sched_url.strip()
            patterns = [
                r'youtu\.be/([A-Za-z0-9_-]{11})',
                r'[?&]v=([A-Za-z0-9_-]{11})',
                r'embed/([A-Za-z0-9_-]{11})',
                r'^([A-Za-z0-9_-]{11})$',
            ]
            for pat in patterns:
                m = re.search(pat, url_or_id)
                if m:
                    vid_id = m.group(1)
                    break
            if vid_id:
                try:
                    import requests as _req
                    r = _req.get(
                        f"https://www.youtube.com/oembed?url=https://youtu.be/{vid_id}&format=json",
                        timeout=5,
                    )
                    title = r.json().get("title", vid_id) if r.status_code == 200 else vid_id
                except Exception:
                    title = vid_id

        if not vid_id:
            st.error("Could not parse a valid video ID. Check the URL.")
        else:
            trigger_dt = datetime(
                sched_date.year, sched_date.month, sched_date.day,
                int(sched_hour), int(sched_min), 0,
            )
            trigger_ts = trigger_dt.timestamp()
            if trigger_ts <= time.time():
                st.error("Scheduled time is in the past! Pick a future time.")
            else:
                label = sched_label or title or vid_id
                events = st.session_state["_sched_events"]
                events.append(
                    {
                        "vid":        vid_id,
                        "title":      title or vid_id,
                        "trigger_ts": trigger_ts,
                        "label":      label,
                        "fired":      False,
                    }
                )
                st.session_state["_sched_events"] = events
                st.success(
                    f"✅ Scheduled **{label}** for "
                    f"{trigger_dt.strftime('%b %d %H:%M')}"
                )
                st.rerun()

    # ── Upcoming schedules list ───────────────────────────────────────────────
    events: list[dict] = st.session_state.get("_sched_events", [])
    pending = [e for e in events if not e.get("fired")]
    fired   = [e for e in events if e.get("fired")]

    if pending:
        st.markdown("##### 📋 Upcoming")
        for i, evt in enumerate(pending):
            col_label, col_cd, col_rm = st.columns([4, 2, 1])
            with col_label:
                title_short = evt["title"][:30] + "…" if len(evt["title"]) > 30 else evt["title"]
                dt_str = datetime.fromtimestamp(evt["trigger_ts"]).strftime("%b %d %H:%M")
                st.markdown(
                    f"<b>{evt.get('label', title_short)}</b><br>"
                    f"<span style='color:#888;font-size:11px'>{dt_str} · {title_short}</span>",
                    unsafe_allow_html=True,
                )
            with col_cd:
                countdown = _format_countdown(evt["trigger_ts"])
                st.markdown(
                    f"<span style='color:#6c63ff;font-family:JetBrains Mono,monospace;font-size:12px'>"
                    f"⏱ {countdown}</span>",
                    unsafe_allow_html=True,
                )
            with col_rm:
                if st.button("×", key=f"sched_rm_{i}_{evt['vid']}", help="Remove"):
                    events.remove(evt)
                    st.session_state["_sched_events"] = events
                    st.rerun()

        # Manual check button
        if st.button("🔔 Check now (fire due schedules)", use_container_width=True):
            fired_any = check_and_fire_scheduled()
            if fired_any:
                st.rerun()
            else:
                st.info("No schedules due yet.")

    if fired:
        with st.expander(f"✅ Fired schedules ({len(fired)})"):
            for evt in fired:
                dt_str = datetime.fromtimestamp(evt["trigger_ts"]).strftime("%b %d %H:%M")
                st.caption(f"✓ {evt.get('label', evt['title'])} — played at {dt_str}")
            if st.button("Clear fired history", key="sched_clr_fired"):
                st.session_state["_sched_events"] = [e for e in events if not e.get("fired")]
                st.rerun()
