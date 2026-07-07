"""
study_focus.py
──────────────
TubePlay feature module: Pomodoro Study Hub & Focus Mode

Integrates:
  • A customizable Pomodoro Timer (Work, Short Break, Long Break).
  • Auto-pausing integration with YouTube player.
  • Focused session tracking and stats dashboard.
  • Integrated ambient Lofi player list.
"""

import streamlit as st
import time

# ── Session State Schema ──────────────────────────────────────────────────────
FOCUS_DEFAULTS = {
    "focus_state": "idle",       # "idle", "running", "paused"
    "focus_mode": "Work",        # "Work", "Short Break", "Long Break"
    "focus_time_left": 1500,     # in seconds (25 mins default)
    "focus_last_tick": 0.0,      # timestamp of last tick check
    "focus_completed": 0,        # count of completed work blocks
    "focus_auto_pause": True,    # auto-pause youtube on break
    "focus_ambient": "None",     # ambient sound name
}

def init_focus_state():
    for k, v in FOCUS_DEFAULTS.items():
        if k not in st.session_state:
            st.session_state[k] = v

def get_mode_duration(mode: str) -> int:
    durations = {"Work": 1500, "Short Break": 300, "Long Break": 900}
    return durations.get(mode, 1500)

def tick_timer() -> bool:
    """Updates the timer countdown. Returns True if state changed (timer ended)."""
    init_focus_state()
    if st.session_state.focus_state != "running":
        return False

    now = time.time()
    elapsed = int(now - st.session_state.focus_last_tick)
    if elapsed >= 1:
        st.session_state.focus_time_left = max(0, st.session_state.focus_time_left - elapsed)
        st.session_state.focus_last_tick = now
        
        # If timer hits zero
        if st.session_state.focus_time_left <= 0:
            st.session_state.focus_state = "idle"
            
            # Action on completion
            if st.session_state.focus_mode == "Work":
                st.session_state.focus_completed += 1
                # Switch to Break
                st.session_state.focus_mode = "Short Break"
                st.session_state.focus_time_left = get_mode_duration("Short Break")
                # Return True to trigger auto-pause check
                return True
            else:
                st.session_state.focus_mode = "Work"
                st.session_state.focus_time_left = get_mode_duration("Work")
                return True
    return False

def render_focus_panel(api_key: str | None = None):
    init_focus_state()
    
    # Run timer tick update
    timer_ended = tick_timer()
    if timer_ended:
        st.toast("🔔 Pomodoro Timer Alert!")
        # If auto-pause is enabled and we just switched to a break, pause the main player
        if st.session_state.focus_auto_pause and st.session_state.focus_mode in ["Short Break", "Long Break"]:
            st.session_state.playing_id = None
            st.session_state.playing_title = ""
            st.success("⏸️ Video auto-paused for your break!")
        st.rerun()

    st.markdown("#### ⏳ Pomodoro Focus Center")
    st.caption("Maximize study productivity by scheduling focus sessions and breaks.")

    # ── Timer display ──
    mins = st.session_state.focus_time_left // 60
    secs = st.session_state.focus_time_left % 60
    timer_str = f"{mins:02d}:{secs:02d}"
    bg_col = "#e84545" if st.session_state.focus_mode == "Work" else "#393e46"
    st.markdown(
        f"""
        <div style="background:{bg_col}22; border: 1px solid {bg_col}55; border-radius:12px; padding:20px; text-align:center; margin-bottom:12px">
          <span style="font-size:13px; font-family: JetBrains Mono; text-transform:uppercase; color:{bg_col}">{st.session_state.focus_mode} Mode</span>
          <h2 style="font-size:3em; font-family: JetBrains Mono; font-weight:700; margin:4px 0 0 0; color:#fff">{timer_str}</h2>
        </div>
        """,
        unsafe_allow_html=True
    )

    # ── Controls (flat — no nested columns) ──
    if st.session_state.focus_state == "running":
        if st.button("⏸ Pause", key="focus_pause_btn", use_container_width=True):
            st.session_state.focus_state = "paused"
            st.rerun()
    else:
        label = "▶ Resume" if st.session_state.focus_state == "paused" else "▶ Start"
        if st.button(label, key="focus_start_btn", use_container_width=True):
            st.session_state.focus_state = "running"
            st.session_state.focus_last_tick = time.time()
            st.rerun()
    if st.button("↺ Reset", key="focus_reset_btn", use_container_width=True):
        st.session_state.focus_state = "idle"
        st.session_state.focus_time_left = get_mode_duration(st.session_state.focus_mode)
        st.rerun()
    next_mode = "Short Break" if st.session_state.focus_mode == "Work" else "Work"
    if st.button(f"⏭ Skip to {next_mode}", key="focus_skip_btn", use_container_width=True):
        st.session_state.focus_state = "idle"
        st.session_state.focus_mode = next_mode
        st.session_state.focus_time_left = get_mode_duration(next_mode)
        st.rerun()

    # ── Stats ──
    st.caption(f"🏆 Completed: {st.session_state.focus_completed} block(s) · ⏱️ {st.session_state.focus_completed * 25} mins")
    auto_p = st.checkbox("Auto-Pause Player on Break", value=st.session_state.focus_auto_pause, key="auto_pause_cb")
    if auto_p != st.session_state.focus_auto_pause:
        st.session_state.focus_auto_pause = auto_p
        st.rerun()

    st.divider()

    # ── Ambient Sounds & Focus Streams ──
    st.markdown("##### 🎵 Focus Ambient Sound Generator")
    st.caption("Play curated lofi streams or white noise directly alongside your study session.")
    
    ambient_options = {
        "None": None,
        "Lofi Hip Hop Radio": "jfKfPfyJRdk",
        "Coffee Shop Ambient / Jazz": "353A1_zV5W4",
        "Gentle Rain Sound": "q76bN0Gy6zo",
        "White Noise for Focus": "nMfPqeZjc2c",
    }
    
    selected_sound = st.selectbox(
        "Select Background Stream", 
        list(ambient_options.keys()), 
        index=list(ambient_options.keys()).index(st.session_state.focus_ambient),
        key="focus_ambient_select"
    )
    
    if selected_sound != st.session_state.focus_ambient:
        st.session_state.focus_ambient = selected_sound
        st.rerun()
        
    ambient_id = ambient_options.get(selected_sound)
    if ambient_id:
        # Embed a tiny background sound player (1 pixel or small size to not clutter UI)
        st.markdown(
            f"""
            <div style="background:#16161e; border: 1px solid #222230; border-radius:10px; padding:12px; display:flex; align-items:center; gap:12px">
              <span style="font-size:1.3em">🔊</span>
              <div style="flex-grow:1">
                <span style="font-size:12px; font-family: JetBrains Mono; color:#888;">Playing Background:</span><br>
                <span style="font-size:13px; font-weight:600; color:#fff;">{selected_sound}</span>
              </div>
              <div style="width:120px; height:60px; overflow:hidden; border-radius:6px;">
                <iframe src="https://www.youtube.com/embed/{ambient_id}?autoplay=1&mute=0&controls=1&volume=40" 
                  width="120" height="60" style="border:none;" allow="autoplay"></iframe>
              </div>
            </div>
            """, 
            unsafe_allow_html=True
        )

    # Trigger a soft rerun if running, to keep countdown timer fresh
    if st.session_state.focus_state == "running":
        time.sleep(1)
        st.rerun()
