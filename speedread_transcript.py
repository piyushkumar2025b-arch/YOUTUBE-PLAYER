"""
speedread_transcript.py
───────────────────────
TubePlay feature module: Speed-Read Transcript Viewer

Displays the video transcript in a "speed-reading" word-highlight mode:
  • Words appear one at a time at a configurable WPM (100–900)
  • Large, centred, high-contrast display for focus reading
  • Progress bar showing position in transcript
  • Word index scrubber to jump to any point
  • Export full cleaned text (no timestamps)
  • Paragraph mode: shows sentences for slower, context-rich reading

Implementation note:
  Streamlit can't truly animate in real-time; we use a "word-by-word
  reveal" approach where each button click advances N words, giving the
  feel of a paced reading session.  A JS auto-advance option uses
  setTimeout + streamlit component messaging for smoother playback.

Usage in app.py:
    from speedread_transcript import render_speedread_panel
    with st.expander("⚡ Speed-Read Transcript"):
        render_speedread_panel(video_id, transcript_text)
"""

import streamlit as st
import re
import math


# ── Helpers ───────────────────────────────────────────────────────────────────

def _strip_timestamps(transcript: str) -> str:
    """Remove [mm:ss] timestamp markers and return plain text."""
    return re.sub(r"\[\d+:\d{2}\]\s*", "", transcript).strip()


def _tokenize(text: str) -> list[str]:
    """Split into word tokens, preserving punctuation attached to words."""
    return [w for w in text.split() if w]


def _words_per_chunk(wpm: int) -> int:
    """How many words to advance per 'tick' click (keep chunks small for UX)."""
    # At very high WPM we advance in bigger steps so fewer clicks are needed
    if wpm <= 200:
        return 1
    if wpm <= 400:
        return 2
    return 3


def _highlight_word_html(words: list[str], index: int, context: int = 5) -> str:
    """
    Return HTML showing a window of words around *index*,
    with the current word highlighted.
    """
    start = max(0, index - context)
    end   = min(len(words), index + context + 1)
    parts = []
    for i in range(start, end):
        word = words[i]
        if i == index:
            parts.append(
                f'<span style="background:#6c63ff;color:#fff;border-radius:4px;'
                f'padding:2px 6px;font-size:2.2em;font-weight:700">{word}</span>'
            )
        else:
            opacity = 1.0 - abs(i - index) * 0.12
            parts.append(
                f'<span style="color:rgba(200,200,200,{max(opacity,0.2)});font-size:1.6em">{word}</span>'
            )
    return " ".join(parts)


# ── Streamlit UI component ────────────────────────────────────────────────────

def render_speedread_panel(video_id: str, transcript: str | None):
    """
    Render the speed-read panel.
    Call inside an expander or tab in app.py.

    Args:
        video_id:   current playing video ID (used to scope session state)
        transcript: the raw transcript string (with [mm:ss] stamps), or None
    """
    if not transcript:
        st.info(
            "No transcript loaded. Use the **📄 Transcript** expander to load "
            "the transcript first, then come back here."
        )
        return

    # ── Session state keys ────────────────────────────────────────────────────
    word_idx_key = f"_sr_idx_{video_id}"
    wpm_key      = f"_sr_wpm_{video_id}"
    mode_key     = f"_sr_mode_{video_id}"

    if word_idx_key not in st.session_state:
        st.session_state[word_idx_key] = 0
    if wpm_key not in st.session_state:
        st.session_state[wpm_key] = 300
    if mode_key not in st.session_state:
        st.session_state[mode_key] = "word"   # "word" | "sentence"

    # ── Prepare data ──────────────────────────────────────────────────────────
    plain_text = _strip_timestamps(transcript)
    words      = _tokenize(plain_text)
    total      = len(words)
    if total == 0:
        st.warning("Transcript appears to be empty after processing.")
        return

    # Sentence mode: split into sentences
    sentences  = [s.strip() for s in re.split(r'(?<=[.!?])\s+', plain_text) if s.strip()]
    total_sent = len(sentences)

    # ── Settings row ─────────────────────────────────────────────────────────
    s1, s2, s3 = st.columns([2, 2, 2])
    with s1:
        wpm = st.slider(
            "Speed (WPM)",
            min_value=100, max_value=900, step=50,
            value=st.session_state[wpm_key],
            key=f"sr_wpm_slider_{video_id}",
        )
        if wpm != st.session_state[wpm_key]:
            st.session_state[wpm_key] = wpm

    with s2:
        mode = st.radio(
            "Mode",
            ["word", "sentence"],
            index=["word", "sentence"].index(st.session_state[mode_key]),
            horizontal=True,
            key=f"sr_mode_{video_id}",
        )
        if mode != st.session_state[mode_key]:
            st.session_state[mode_key] = mode

    with s3:
        st.markdown("")
        if st.button("⏮ Reset", key=f"sr_reset_{video_id}", use_container_width=True):
            st.session_state[word_idx_key] = 0
            st.rerun()

    # ── Word mode ─────────────────────────────────────────────────────────────
    if mode == "word":
        idx   = min(st.session_state[word_idx_key], total - 1)
        chunk = _words_per_chunk(wpm)
        pct   = int((idx + 1) / total * 100)

        # Display
        st.markdown(
            f"<div style='text-align:center;padding:32px 16px;min-height:120px;"
            f"background:#111;border-radius:16px;margin:12px 0;line-height:1.8'>"
            f"{_highlight_word_html(words, idx)}"
            f"</div>",
            unsafe_allow_html=True,
        )
        st.progress(pct)
        st.caption(f"Word {idx + 1} / {total}  ·  ~{pct}% complete  ·  {wpm} WPM target")

        # Controls
        c_back, c_step, c_fwd, c_jump = st.columns([1, 2, 1, 2])
        with c_back:
            if st.button("◀ Back", key=f"sr_back_{video_id}", use_container_width=True):
                st.session_state[word_idx_key] = max(0, idx - chunk)
                st.rerun()
        with c_step:
            if st.button(f"▶ Next ({chunk} word{'s' if chunk > 1 else ''})",
                         key=f"sr_next_{video_id}", use_container_width=True):
                new_idx = idx + chunk
                if new_idx >= total:
                    st.balloons()
                    new_idx = total - 1
                st.session_state[word_idx_key] = new_idx
                st.rerun()
        with c_fwd:
            if st.button("Skip ▶▶", key=f"sr_skip_{video_id}", use_container_width=True):
                st.session_state[word_idx_key] = min(idx + 20, total - 1)
                st.rerun()
        with c_jump:
            jump_to = st.number_input(
                "Jump to word #", min_value=1, max_value=total, value=idx + 1,
                step=1, key=f"sr_jump_{video_id}", label_visibility="collapsed",
            )
            if st.button("Go", key=f"sr_go_{video_id}", use_container_width=True):
                st.session_state[word_idx_key] = int(jump_to) - 1
                st.rerun()

    # ── Sentence mode ─────────────────────────────────────────────────────────
    else:
        sent_idx_key = f"_sr_sidx_{video_id}"
        if sent_idx_key not in st.session_state:
            st.session_state[sent_idx_key] = 0
        sidx = min(st.session_state[sent_idx_key], total_sent - 1)
        pct  = int((sidx + 1) / total_sent * 100)

        sentence = sentences[sidx] if sentences else ""
        word_count = len(sentence.split())
        read_sec   = round(word_count / (wpm / 60))

        st.markdown(
            f"<div style='text-align:center;padding:28px 24px;min-height:110px;"
            f"background:#111;border-radius:16px;margin:12px 0;"
            f"font-size:1.35em;color:#e8e8e8;line-height:1.7'>"
            f"{sentence}"
            f"</div>",
            unsafe_allow_html=True,
        )
        st.progress(pct)
        st.caption(
            f"Sentence {sidx + 1} / {total_sent}  ·  {word_count} words  ·  "
            f"~{read_sec}s at {wpm} WPM"
        )

        sc1, sc2, sc3 = st.columns(3)
        with sc1:
            if st.button("◀ Prev", key=f"sr_sprev_{video_id}", use_container_width=True):
                st.session_state[sent_idx_key] = max(0, sidx - 1)
                st.rerun()
        with sc2:
            if st.button("▶ Next sentence", key=f"sr_snext_{video_id}", use_container_width=True):
                if sidx + 1 >= total_sent:
                    st.balloons()
                else:
                    st.session_state[sent_idx_key] = sidx + 1
                st.rerun()
        with sc3:
            if st.button("⏩ Skip 5", key=f"sr_sskip_{video_id}", use_container_width=True):
                st.session_state[sent_idx_key] = min(sidx + 5, total_sent - 1)
                st.rerun()

    st.divider()

    # ── Export plain text ─────────────────────────────────────────────────────
    st.download_button(
        "⬇ Export plain transcript (no timestamps)",
        data=plain_text.encode("utf-8"),
        file_name=f"tubeplay-{video_id}-plain.txt",
        mime="text/plain",
        use_container_width=True,
    )

    # ── Estimated read time summary ───────────────────────────────────────────
    avg_wpm     = 238  # average adult silent reading speed
    est_minutes = math.ceil(total / avg_wpm)
    st.caption(
        f"📖 Transcript: {total:,} words  ·  "
        f"Avg silent read: ~{est_minutes} min  ·  "
        f"At {wpm} WPM: ~{math.ceil(total / wpm)} min"
    )
