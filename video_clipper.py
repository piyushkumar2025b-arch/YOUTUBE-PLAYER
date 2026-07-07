"""
video_clipper.py
────────────────
TubePlay feature module: Video Clipper and Custom Chapters Creator

Allows users to:
  • Define custom clips/chapters for the playing video with start and end timestamps.
  • Play a specific clip (sets start time and loops).
  • Import chapters from standard YouTube timestamp description format.
  • Export custom chapters as Markdown or YouTube description text.
"""

import streamlit as st
import re

# ── Session State Init ───────────────────────────────────────────────────────
if "video_clips" not in st.session_state:
    st.session_state.video_clips = {}  # video_id -> list of {"title": str, "start": int, "end": int}

def time_to_sec(t_str: str) -> int:
    """Convert MM:SS or HH:MM:SS or integer string to seconds."""
    t_str = t_str.strip()
    if not t_str:
        return 0
    if re.match(r"^\d+$", t_str):
        return int(t_str)
    
    parts = t_str.split(":")
    try:
        if len(parts) == 2:
            return int(parts[0]) * 60 + int(parts[1])
        elif len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
    except ValueError:
        pass
    return 0

def sec_to_time(seconds: int) -> str:
    """Convert seconds to MM:SS or HH:MM:SS format."""
    if seconds < 3600:
        return f"{seconds // 60}:{seconds % 60:02d}"
    return f"{seconds // 3600}:{(seconds % 3600) // 60:02d}:{seconds % 60:02d}"

def render_clipper_panel(video_id: str, title: str):
    st.markdown("#### ✂️ Video Clipper & Chapters")
    st.caption("Create custom segments, study loops, or bookmarks for this video.")

    clips = st.session_state.video_clips.setdefault(video_id, [])

    # ── Add Clip Form ──
    with st.form("add_clip_form", clear_on_submit=True):
        st.markdown("##### Create New Segment/Loop")
        col1, col2, col3 = st.columns([3, 1, 1])
        with col1:
            clip_title = st.text_input("Segment Title", placeholder="e.g. Coding Section, Solo Solo...")
        with col2:
            clip_start = st.text_input("Start Time", placeholder="1:15 or 75", help="Format: MM:SS or seconds")
        with col3:
            clip_end = st.text_input("End Time (Opt)", placeholder="2:30 or 150", help="Optional loop end time")
        
        submit = st.form_submit_button("Add Segment", use_container_width=True)
        if submit:
            if not clip_title:
                st.error("Please provide a segment title.")
            else:
                start_sec = time_to_sec(clip_start)
                end_sec = time_to_sec(clip_end) if clip_end else 0
                if end_sec > 0 and end_sec <= start_sec:
                    st.error("End time must be greater than start time.")
                else:
                    clips.append({
                        "title": clip_title,
                        "start": start_sec,
                        "end": end_sec
                    })
                    # Sort clips by start time
                    clips.sort(key=lambda x: x["start"])
                    st.session_state.video_clips[video_id] = clips
                    st.success(f"Added segment: '{clip_title}'")
                    st.rerun()

    # ── Import Chapters ──
    with st.expander("📥 Import Chapters (YouTube Format)"):
        st.caption("Paste a description containing timestamps (e.g. '01:23 Introduction') to automatically generate chapters.")
        import_text = st.text_area("Paste text here", height=100, key=f"import_clip_{video_id}", placeholder="0:00 Intro\n1:45 Demo Section\n05:10 Deep Dive")
        if st.button("Parse and Import", key=f"import_btn_{video_id}", use_container_width=True):
            imported = 0
            lines = import_text.splitlines()
            for line in lines:
                # Look for timestamps like 01:23, 1:23:45, 12:34
                match = re.search(r"(\d{1,2}:\d{2}(?::\d{2})?)", line)
                if match:
                    ts_str = match.group(1)
                    # The title is everything else in the line
                    t_title = line.replace(ts_str, "").strip(" -:[]()")
                    if not t_title:
                        t_title = f"Chapter @ {ts_str}"
                    start_sec = time_to_sec(ts_str)
                    clips.append({
                        "title": t_title,
                        "start": start_sec,
                        "end": 0
                    })
                    imported += 1
            if imported > 0:
                clips.sort(key=lambda x: x["start"])
                st.session_state.video_clips[video_id] = clips
                st.success(f"Successfully imported {imported} chapters!")
                st.rerun()
            else:
                st.warning("No valid timestamps found.")

    st.divider()

    # ── Display Clips ──
    if not clips:
        st.info("No segments created yet. Use the form above to add custom chapters or bookmarks.")
        return

    st.markdown("##### Custom Segments List")
    
    # Header links for sharing/exporting
    c_exp, c_clr = st.columns([3, 1])
    with c_exp:
        md_text = f"### Custom Chapters for: {title}\n\n"
        desc_text = ""
        for c in clips:
            md_text += f"- [{sec_to_time(c['start'])}](https://youtu.be/{video_id}?t={c['start']}) - {c['title']}\n"
            desc_text += f"{sec_to_time(c['start'])} {c['title']}\n"
        
        st.download_button(
            "Export Chapters (TXT)",
            data=desc_text.encode("utf-8"),
            file_name=f"tubeplay-{video_id}-chapters.txt",
            mime="text/plain",
            use_container_width=True
        )
    with c_clr:
        if st.button("Clear All", key=f"clear_clips_{video_id}", use_container_width=True):
            st.session_state.video_clips[video_id] = []
            st.success("Cleared all segments.")
            st.rerun()

    st.markdown("")

    for idx, c in enumerate(clips):
        c_play, c_info, c_action = st.columns([1, 4, 1])
        with c_play:
            if st.button("▶", key=f"play_clip_{video_id}_{idx}", help="Jump to start time"):
                st.session_state["start_t"] = c["start"]
                # Store active clip information to loop/play
                if c["end"] > 0:
                    st.session_state["clip_active_loop"] = {
                        "video_id": video_id,
                        "start": c["start"],
                        "end": c["end"],
                        "title": c["title"]
                    }
                else:
                    st.session_state.pop("clip_active_loop", None)
                st.rerun()
        with c_info:
            time_label = sec_to_time(c["start"])
            if c["end"] > 0:
                time_label += f" 🔁 {sec_to_time(c['end'])}"
            st.markdown(f"**{c['title']}** &nbsp; <span style='color:#888; font-family: JetBrains Mono; font-size:12px;'>({time_label})</span>", unsafe_allow_html=True)
        with c_action:
            if st.button("✕", key=f"delete_clip_{video_id}_{idx}", help="Delete segment"):
                clips.pop(idx)
                st.session_state.video_clips[video_id] = clips
                st.rerun()
