"""
video_summarizer.py
───────────────────
TubePlay feature module: Smart Transcript Summarizer & Key Takeaways Generator

Analyzes the video transcript and produces:
  • Key Topics (Word cloud style tags).
  • High-impact summary bullet points with click-to-jump timestamp links.
  • Sentiment score and readability statistics.
  • Gemini AI-powered summarization if a Google API Key is provided.
"""

import streamlit as st
import re
import collections
import urllib.parse

# ── English Stopwords List for Offline Analysis ─────────────────────────────
STOPWORDS = {
    "i", "me", "my", "myself", "we", "our", "ours", "ourselves", "you", "your", 
    "yours", "yourself", "yourselves", "he", "him", "his", "himself", "she", 
    "her", "hers", "herself", "it", "its", "itself", "they", "them", "their", 
    "theirs", "themselves", "what", "which", "who", "whom", "this", "that", 
    "these", "those", "am", "is", "are", "was", "were", "be", "been", "being", 
    "have", "has", "had", "having", "do", "does", "did", "doing", "a", "an", 
    "the", "and", "but", "if", "or", "because", "as", "until", "while", "of", 
    "at", "by", "for", "with", "about", "against", "between", "into", "through", 
    "during", "before", "after", "above", "below", "to", "from", "up", "down", 
    "in", "out", "on", "off", "over", "under", "again", "further", "then", "once", 
    "here", "there", "when", "where", "why", "how", "all", "any", "both", "each", 
    "few", "more", "most", "other", "some", "such", "no", "nor", "not", "only", 
    "own", "same", "so", "than", "too", "very", "s", "t", "can", "will", "just", 
    "don", "should", "now", "like", "get", "go", "make", "would", "know", "think",
    "see", "say", "us", "one", "two", "well", "also", "want", "people", "video"
}

def clean_and_tokenize(text: str) -> list[str]:
    """Helper to tokenize and lowercase words, removing special characters."""
    words = re.findall(r"\b[a-zA-Z]{3,}\b", text.lower())
    return [w for w in words if w not in STOPWORDS]

def local_summarize(transcript: str, num_bullets: int = 5) -> tuple[list[dict], list[str], dict]:
    """
    Offline Rule-based TF-IDF/Sentence scoring summarization.
    Extracts key topics and selects high-score sentences aligned with their timestamps.
    """
    lines = [line.strip() for line in transcript.splitlines() if line.strip()]
    parsed_lines = []
    full_text_list = []
    
    for line in lines:
        # Extract timestamp in format [MM:SS] or similar
        match = re.match(r"^\[(\d{1,2}:\d{2}(?::\d{2})?)\]\s*(.*)", line)
        if match:
            stamp, text = match.group(1), match.group(2)
            parsed_lines.append({"time": stamp, "text": text})
            full_text_list.append(text)
        else:
            parsed_lines.append({"time": "0:00", "text": line})
            full_text_list.append(line)
            
    full_text = " ".join(full_text_list)
    tokens = clean_and_tokenize(full_text)
    
    # Calculate word frequency
    word_freq = collections.Counter(tokens)
    most_common_topics = [word for word, count in word_freq.most_common(8)]
    
    # Score sentences based on word frequency
    sentence_scores = []
    for idx, item in enumerate(parsed_lines):
        sentence_tokens = clean_and_tokenize(item["text"])
        if len(sentence_tokens) < 5:  # skip very short phrases
            continue
        score = sum(word_freq[w] for w in sentence_tokens) / (len(sentence_tokens) ** 0.5)
        # boost sentences that contain top topics
        for topic in most_common_topics[:3]:
            if topic in sentence_tokens:
                score *= 1.2
        sentence_scores.append({"idx": idx, "score": score, "time": item["time"], "text": item["text"]})
        
    # Sort and pick top sentences
    sentence_scores.sort(key=lambda x: x["score"], reverse=True)
    top_bullets = sentence_scores[:num_bullets]
    # Re-sort top bullets chronologically
    top_bullets.sort(key=lambda x: x["idx"])
    
    # Calculate simple stats
    total_words = len(full_text.split())
    read_mins = max(1, round(total_words / 200)) # Avg reading speed 200 wpm
    
    stats = {
        "words": total_words,
        "read_time": read_mins,
        "sentences": len(parsed_lines)
    }
    
    return top_bullets, most_common_topics, stats

def gemini_summarize(transcript: str, api_key: str) -> str:
    """Summarize transcript using Gemini 2.5 Flash API via REST request."""
    import requests
    # Limit transcript size to avoid token limit issues in REST request
    truncated_transcript = transcript[:15000]
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
    headers = {"Content-Type": "application/json"}
    prompt = (
        "You are a helpful YouTube learning assistant. Summarize the following video transcript. "
        "Provide a concise summary, key takeaways, and outline the main sections with their timestamps "
        "in format [MM:SS] if present. Return the output as clean markdown.\n\n"
        f"Transcript:\n{truncated_transcript}"
    )
    data = {
        "contents": [
            {
                "parts": [
                    {"text": prompt}
                ]
            }
        ]
    }
    
    try:
        r = requests.post(url, headers=headers, json=data, timeout=20)
        if r.status_code == 200:
            res_json = r.json()
            return res_json["candidates"][0]["content"]["parts"][0]["text"]
        else:
            return f"❌ Gemini API Error {r.status_code}: {r.text[:300]}"
    except Exception as e:
        return f"❌ Failed to reach Gemini API: {e}"

def render_summarizer_panel(video_id: str, transcript: str | None, api_key: str | None):
    st.markdown("#### ⚡ Smart Transcript Summarizer")
    st.caption("AI-powered and local heuristic transcript analyzer for instant key insights.")

    if not transcript:
        st.info("Please load the video transcript first using the expander above.")
        return

    # ── Choice of Summarization Mode ──
    mode = st.radio(
        "Summarization Method",
        ["Offline Keywords & Highlights (Instant)", "Gemini AI Summary (Requires Key)"],
        horizontal=True,
        key=f"sum_mode_{video_id}"
    )

    if mode == "Offline Keywords & Highlights (Instant)":
        bullets, topics, stats = local_summarize(transcript)

        # ── Display Stats ──
        c1, c2, c3 = st.columns(3)
        with c1:
            st.metric("Total Words", stats["words"])
        with c2:
            st.metric("Est. Reading Time", f"{stats['read_time']} min")
        with c3:
            st.metric("Segment Count", stats["sentences"])

        # ── Display Topics ──
        if topics:
            st.markdown("##### 🏷️ Main Topics Detected")
            topics_html = " ".join([f"<span class='pill-accent'>#{t}</span>" for t in topics])
            st.markdown(topics_html, unsafe_allow_html=True)
            st.write("")

        # ── Display Summary Bullet Points with Timestamp Click Actions ──
        st.markdown("##### 📌 Key Highlights (Click timestamp to jump)")
        for b in bullets:
            col_t, col_text = st.columns([1, 8])
            with col_t:
                # Convert MM:SS to seconds for click action
                time_str = b["time"]
                parts = time_str.split(":")
                secs = 0
                try:
                    if len(parts) == 2:
                        secs = int(parts[0]) * 60 + int(parts[1])
                    elif len(parts) == 3:
                        secs = int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
                except ValueError:
                    pass
                
                if st.button(f"⏱️ {time_str}", key=f"sum_t_{video_id}_{secs}", help="Jump to this time"):
                    st.session_state["start_t"] = secs
                    st.rerun()
            with col_text:
                st.markdown(f"{b['text']}")

    else:
        # Gemini AI Summary Mode
        gemini_key = st.text_input(
            "Enter Gemini/Google API Key",
            type="password",
            placeholder="AIzaSy...",
            value=api_key if api_key else "",
            help="Get a free key from Google AI Studio",
            key=f"gem_key_input_{video_id}"
        )
        
        if not gemini_key:
            st.warning("Please provide a Google API Key in the field above or in the sidebar.")
        else:
            if st.button("Generate AI Summary", key=f"gen_ai_sum_{video_id}", use_container_width=True):
                with st.spinner("Generating AI Summary using Gemini..."):
                    summary = gemini_summarize(transcript, gemini_key)
                st.session_state[f"gemini_summary_{video_id}"] = summary
            
            summary_cache = st.session_state.get(f"gemini_summary_{video_id}")
            if summary_cache:
                st.markdown("##### 🤖 Gemini Takeaways Summary")
                st.markdown(summary_cache)
                
                # Download Button for the summary
                st.download_button(
                    "Download AI Summary",
                    data=summary_cache.encode("utf-8"),
                    file_name=f"tubeplay-{video_id}-ai-summary.md",
                    mime="text/markdown",
                    use_container_width=True
                )
