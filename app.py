import streamlit as st
import requests
import re
import urllib.parse

# ─── Page Config ────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="TubePlay — In-Site YouTube Player",
    page_icon="▶️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── Styles ──────────────────────────────────────────────────────────────────
st.markdown("""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;700&family=JetBrains+Mono:wght@400;500&display=swap');

  /* ── Base ── */
  html, body, [data-testid="stApp"] {
      background: #0d0d0f !important;
      color: #e8e8e8;
      font-family: 'Space Grotesk', sans-serif;
  }

  /* ── Sidebar ── */
  [data-testid="stSidebar"] {
      background: #111116 !important;
      border-right: 1px solid #222230;
  }
  [data-testid="stSidebar"] * { color: #e8e8e8 !important; }

  /* ── Inputs ── */
  .stTextInput > div > div > input,
  .stTextArea > div > div > textarea {
      background: #1a1a24 !important;
      border: 1px solid #2e2e45 !important;
      color: #e8e8e8 !important;
      border-radius: 8px !important;
      font-family: 'JetBrains Mono', monospace !important;
      font-size: 13px !important;
  }
  .stTextInput > div > div > input:focus,
  .stTextArea > div > div > textarea:focus {
      border-color: #6c63ff !important;
      box-shadow: 0 0 0 2px rgba(108,99,255,0.25) !important;
  }

  /* ── Buttons ── */
  .stButton > button {
      background: #6c63ff !important;
      color: #fff !important;
      border: none !important;
      border-radius: 8px !important;
      font-family: 'Space Grotesk', sans-serif !important;
      font-weight: 600 !important;
      font-size: 14px !important;
      padding: 10px 22px !important;
      transition: background 0.2s, transform 0.1s !important;
  }
  .stButton > button:hover {
      background: #5a52e8 !important;
      transform: translateY(-1px) !important;
  }
  .stButton > button:active { transform: translateY(0) !important; }

  /* ── Cards ── */
  .video-card {
      background: #16161e;
      border: 1px solid #222230;
      border-radius: 12px;
      overflow: hidden;
      cursor: pointer;
      transition: border-color 0.2s, transform 0.15s, box-shadow 0.2s;
      margin-bottom: 12px;
  }
  .video-card:hover {
      border-color: #6c63ff;
      transform: translateY(-2px);
      box-shadow: 0 8px 24px rgba(108,99,255,0.15);
  }
  .video-card img { width: 100%; display: block; }
  .video-card-body { padding: 10px 12px 12px; }
  .video-card-title {
      font-size: 13px;
      font-weight: 600;
      color: #e8e8e8;
      line-height: 1.4;
      margin: 0 0 4px;
      display: -webkit-box;
      -webkit-line-clamp: 2;
      -webkit-box-orient: vertical;
      overflow: hidden;
  }
  .video-card-meta {
      font-size: 11px;
      color: #666;
      font-family: 'JetBrains Mono', monospace;
  }

  /* ── Player wrapper ── */
  .player-wrap {
      background: #000;
      border-radius: 16px;
      overflow: hidden;
      aspect-ratio: 16/9;
      width: 100%;
      box-shadow: 0 20px 60px rgba(0,0,0,0.6);
  }
  .player-wrap iframe { width:100%; height:100%; border:none; display:block; }

  /* ── Pill badge ── */
  .pill {
      display: inline-block;
      background: #1e1e2e;
      border: 1px solid #2e2e45;
      border-radius: 20px;
      padding: 3px 10px;
      font-size: 11px;
      color: #9090c0;
      font-family: 'JetBrains Mono', monospace;
      margin-right: 6px;
  }

  /* ── Section headers ── */
  h1 { font-family:'Space Grotesk',sans-serif !important; font-weight:700 !important; }
  h2,h3 { font-family:'Space Grotesk',sans-serif !important; font-weight:600 !important; }

  /* ── Hide streamlit chrome ── */
  #MainMenu, footer, header { visibility: hidden; }
  .block-container { padding-top: 1.5rem !important; }
</style>
""", unsafe_allow_html=True)


# ─── Helpers ─────────────────────────────────────────────────────────────────
def extract_video_id(url_or_id: str) -> str | None:
    """Extract YouTube video ID from URL or return raw ID."""
    url_or_id = url_or_id.strip()
    # Already an 11-char ID
    if re.match(r'^[A-Za-z0-9_-]{11}$', url_or_id):
        return url_or_id
    # youtu.be short link
    m = re.search(r'youtu\.be/([A-Za-z0-9_-]{11})', url_or_id)
    if m:
        return m.group(1)
    # youtube.com/watch?v=
    m = re.search(r'[?&]v=([A-Za-z0-9_-]{11})', url_or_id)
    if m:
        return m.group(1)
    # youtube.com/embed/
    m = re.search(r'embed/([A-Za-z0-9_-]{11})', url_or_id)
    if m:
        return m.group(1)
    return None


def search_youtube(query: str, api_key: str, max_results: int = 12):
    """Search YouTube using Data API v3 (free tier, 100 units/day base)."""
    url = "https://www.googleapis.com/youtube/v3/search"
    params = {
        "part": "snippet",
        "q": query,
        "type": "video",
        "maxResults": max_results,
        "key": api_key,
    }
    try:
        r = requests.get(url, params=params, timeout=8)
        if r.status_code == 403:
            return None, "❌ API key error or quota exceeded. Check your key."
        if r.status_code != 200:
            return None, f"❌ API error {r.status_code}: {r.json().get('error',{}).get('message','Unknown')}"
        data = r.json()
        return data.get("items", []), None
    except Exception as e:
        return None, f"❌ Request failed: {e}"


def get_video_info(video_id: str, api_key: str):
    """Fetch snippet + statistics for a single video."""
    url = "https://www.googleapis.com/youtube/v3/videos"
    params = {"part": "snippet,statistics", "id": video_id, "key": api_key}
    try:
        r = requests.get(url, params=params, timeout=8)
        if r.status_code != 200:
            return None
        items = r.json().get("items", [])
        return items[0] if items else None
    except Exception:
        return None


def embed_html(video_id: str, autoplay: bool = True) -> str:
    params = urllib.parse.urlencode({
        "autoplay": int(autoplay),
        "rel": 0,
        "modestbranding": 1,
        "enablejsapi": 1,
    })
    return f"""
    <div class="player-wrap">
      <iframe
        src="https://www.youtube.com/embed/{video_id}?{params}"
        allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
        allowfullscreen
      ></iframe>
    </div>
    """


def fmt_count(n):
    n = int(n)
    if n >= 1_000_000:
        return f"{n/1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n/1_000:.0f}K"
    return str(n)


# ─── Session State ────────────────────────────────────────────────────────────
if "playing_id" not in st.session_state:
    st.session_state.playing_id = None
if "playing_title" not in st.session_state:
    st.session_state.playing_title = ""
if "search_results" not in st.session_state:
    st.session_state.search_results = []
if "history" not in st.session_state:
    st.session_state.history = []


# ─── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## ▶️ TubePlay")
    st.markdown("<p style='color:#666;font-size:13px;margin-top:-8px'>YouTube player for your site</p>", unsafe_allow_html=True)
    st.divider()

    st.markdown("#### 🔑 API Key")
    st.markdown("<p style='color:#666;font-size:12px'>Free: <a href='https://console.developers.google.com' style='color:#6c63ff'>console.developers.google.com</a><br>Enable <b>YouTube Data API v3</b></p>", unsafe_allow_html=True)
    api_key = st.text_input("YouTube Data API v3 key", type="password", placeholder="AIza...", key="api_key_input")

    st.divider()

    st.markdown("#### 🔗 Play by URL / ID")
    direct_url = st.text_input("YouTube URL or Video ID", placeholder="https://youtu.be/... or dQw4w9WgXcQ", key="direct_url")
    col_a, col_b = st.columns([1, 1])
    with col_a:
        if st.button("▶ Play", use_container_width=True):
            vid = extract_video_id(direct_url)
            if vid:
                st.session_state.playing_id = vid
                st.session_state.playing_title = vid
                if api_key:
                    info = get_video_info(vid, api_key)
                    if info:
                        st.session_state.playing_title = info["snippet"]["title"]
                if vid not in [h[0] for h in st.session_state.history]:
                    st.session_state.history.insert(0, (vid, st.session_state.playing_title))
                    st.session_state.history = st.session_state.history[:10]
                st.rerun()
            else:
                st.error("Invalid URL/ID")

    st.divider()

    # Watch history
    if st.session_state.history:
        st.markdown("#### 🕒 Recent")
        for vid_id, title in st.session_state.history[:5]:
            if st.button(f"{'▶ ' if vid_id == st.session_state.playing_id else ''}{title[:30]}…" if len(title) > 30 else f"{'▶ ' if vid_id == st.session_state.playing_id else ''}{title}", key=f"hist_{vid_id}", use_container_width=True):
                st.session_state.playing_id = vid_id
                st.session_state.playing_title = title
                st.rerun()


# ─── Main Content ─────────────────────────────────────────────────────────────
st.markdown("## In-Site YouTube Player")

# Player section
if st.session_state.playing_id:
    vid = st.session_state.playing_id
    col_player, col_info = st.columns([3, 1])

    with col_player:
        st.markdown(embed_html(vid), unsafe_allow_html=True)

    with col_info:
        st.markdown(f"**{st.session_state.playing_title}**")
        if api_key:
            info = get_video_info(vid, api_key)
            if info:
                snip = info["snippet"]
                stats = info.get("statistics", {})
                st.markdown(f"""
                <div class="pill">👁 {fmt_count(stats.get('viewCount','0'))}</div>
                <div class="pill">👍 {fmt_count(stats.get('likeCount','0'))}</div>
                <br><br>
                <p style="font-size:12px;color:#888;">{snip.get('channelTitle','')}</p>
                <p style="font-size:12px;color:#666;line-height:1.5">{snip.get('description','')[:280]}{"…" if len(snip.get('description',''))>280 else ""}</p>
                """, unsafe_allow_html=True)
        st.markdown(f"""
        <p style="font-size:12px;color:#555;margin-top:12px">
          <a href="https://youtu.be/{vid}" style="color:#6c63ff" target="_blank">↗ Open on YouTube</a>
        </p>
        """, unsafe_allow_html=True)

    st.divider()

else:
    st.info("▶ Paste a YouTube URL in the sidebar, or search below to start playing.")
    st.markdown("")

# ─── Search ──────────────────────────────────────────────────────────────────
st.markdown("#### 🔍 Search YouTube")

if not api_key:
    st.warning("Add your free YouTube Data API v3 key in the sidebar to enable search.")
else:
    search_col, btn_col = st.columns([5, 1])
    with search_col:
        query = st.text_input("Search query", placeholder="lo-fi hip hop, coding music, tutorials…", label_visibility="collapsed", key="search_query")
    with btn_col:
        do_search = st.button("Search", use_container_width=True)

    if do_search and query:
        with st.spinner("Searching…"):
            results, err = search_youtube(query, api_key)
        if err:
            st.error(err)
        elif results:
            st.session_state.search_results = results
        else:
            st.info("No results found.")

    if st.session_state.search_results:
        st.markdown(f"<p style='color:#666;font-size:13px'>Showing {len(st.session_state.search_results)} results — click any card to play</p>", unsafe_allow_html=True)
        cols = st.columns(4)
        for i, item in enumerate(st.session_state.search_results):
            vid_id = item["id"]["videoId"]
            snip = item["snippet"]
            thumb = snip["thumbnails"].get("medium", snip["thumbnails"].get("default", {})).get("url", "")
            title = snip.get("title", "Untitled")
            channel = snip.get("channelTitle", "")

            with cols[i % 4]:
                # Thumbnail button
                if thumb:
                    st.markdown(f"""
                    <div class="video-card">
                      <img src="{thumb}" alt="{title}">
                      <div class="video-card-body">
                        <p class="video-card-title">{title}</p>
                        <span class="video-card-meta">{channel}</span>
                      </div>
                    </div>
                    """, unsafe_allow_html=True)

                short = title[:24] + "…" if len(title) > 24 else title
                if st.button(f"▶ {short}", key=f"play_{vid_id}", use_container_width=True):
                    st.session_state.playing_id = vid_id
                    st.session_state.playing_title = title
                    if vid_id not in [h[0] for h in st.session_state.history]:
                        st.session_state.history.insert(0, (vid_id, title))
                        st.session_state.history = st.session_state.history[:10]
                    st.rerun()

# ─── No API fallback info ─────────────────────────────────────────────────────
with st.expander("ℹ️ How to get a free YouTube Data API v3 key (takes 2 min)"):
    st.markdown("""
1. Go to [console.developers.google.com](https://console.developers.google.com)
2. Create a new project (or select an existing one)
3. Click **Enable APIs & Services** → search **YouTube Data API v3** → Enable
4. Go to **Credentials** → **Create Credentials** → **API Key**
5. Copy the key and paste it in the sidebar

**Free quota:** 10,000 units/day — each search uses ~100 units (≈100 searches/day free).  
Playing videos via the embed player uses **zero API quota** — it's free always!
    """)
