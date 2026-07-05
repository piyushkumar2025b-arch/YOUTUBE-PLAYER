import streamlit as st
import requests
import re
import urllib.parse
import json

# ─── Page Config ────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="TubePlay — In-Site YouTube Player",
    page_icon="▶️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── Session State Init ───────────────────────────────────────────────────────
if "playing_id" not in st.session_state:
    st.session_state.playing_id = None
if "playing_title" not in st.session_state:
    st.session_state.playing_title = ""
if "search_results" not in st.session_state:
    st.session_state.search_results = []
if "history" not in st.session_state:
    st.session_state.history = []
if "queue" not in st.session_state:
    st.session_state.queue = []          # list of (vid_id, title)
if "queue_index" not in st.session_state:
    st.session_state.queue_index = 0
if "theater_mode" not in st.session_state:
    st.session_state.theater_mode = False
if "dark_mode" not in st.session_state:
    st.session_state.dark_mode = True
if "mini_player" not in st.session_state:
    st.session_state.mini_player = False

# ─── Theme Colors ─────────────────────────────────────────────────────────────
if st.session_state.dark_mode:
    BG         = "#0d0d0f"
    SIDEBAR_BG = "#111116"
    CARD_BG    = "#16161e"
    BORDER     = "#222230"
    BORDER2    = "#2e2e45"
    TEXT       = "#e8e8e8"
    MUTED      = "#666"
    MUTED2     = "#888"
    INPUT_BG   = "#1a1a24"
    PILL_BG    = "#1e1e2e"
    PILL_TXT   = "#9090c0"
    ACCENT     = "#6c63ff"
    ACCENT_HOV = "#5a52e8"
else:
    BG         = "#f5f5fa"
    SIDEBAR_BG = "#ebebf5"
    CARD_BG    = "#ffffff"
    BORDER     = "#dddde8"
    BORDER2    = "#c0c0d8"
    TEXT       = "#1a1a2e"
    MUTED      = "#888"
    MUTED2     = "#666"
    INPUT_BG   = "#ffffff"
    PILL_BG    = "#e8e8f5"
    PILL_TXT   = "#5555aa"
    ACCENT     = "#6c63ff"
    ACCENT_HOV = "#5a52e8"

# ─── Styles ──────────────────────────────────────────────────────────────────
st.markdown(f"""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;700&family=JetBrains+Mono:wght@400;500&display=swap');

  html, body, [data-testid="stApp"] {{
      background: {BG} !important;
      color: {TEXT};
      font-family: 'Space Grotesk', sans-serif;
  }}

  [data-testid="stSidebar"] {{
      background: {SIDEBAR_BG} !important;
      border-right: 1px solid {BORDER};
  }}
  [data-testid="stSidebar"] * {{ color: {TEXT} !important; }}

  .stTextInput > div > div > input,
  .stTextArea > div > div > textarea {{
      background: {INPUT_BG} !important;
      border: 1px solid {BORDER2} !important;
      color: {TEXT} !important;
      border-radius: 8px !important;
      font-family: 'JetBrains Mono', monospace !important;
      font-size: 13px !important;
  }}
  .stTextInput > div > div > input:focus,
  .stTextArea > div > div > textarea:focus {{
      border-color: {ACCENT} !important;
      box-shadow: 0 0 0 2px rgba(108,99,255,0.25) !important;
  }}

  .stButton > button {{
      background: {ACCENT} !important;
      color: #fff !important;
      border: none !important;
      border-radius: 8px !important;
      font-family: 'Space Grotesk', sans-serif !important;
      font-weight: 600 !important;
      font-size: 14px !important;
      padding: 10px 22px !important;
      transition: background 0.2s, transform 0.1s !important;
  }}
  .stButton > button:hover {{
      background: {ACCENT_HOV} !important;
      transform: translateY(-1px) !important;
  }}

  /* ghost button variant for secondary actions */
  .btn-ghost > button {{
      background: transparent !important;
      border: 1px solid {BORDER2} !important;
      color: {TEXT} !important;
  }}
  .btn-ghost > button:hover {{
      border-color: {ACCENT} !important;
      color: {ACCENT} !important;
  }}

  .video-card {{
      background: {CARD_BG};
      border: 1px solid {BORDER};
      border-radius: 12px;
      overflow: hidden;
      cursor: pointer;
      transition: border-color 0.2s, transform 0.15s, box-shadow 0.2s;
      margin-bottom: 12px;
  }}
  .video-card:hover {{
      border-color: {ACCENT};
      transform: translateY(-2px);
      box-shadow: 0 8px 24px rgba(108,99,255,0.15);
  }}
  .video-card img {{ width: 100%; display: block; }}
  .video-card-body {{ padding: 10px 12px 12px; }}
  .video-card-title {{
      font-size: 13px; font-weight: 600;
      color: {TEXT}; line-height: 1.4; margin: 0 0 4px;
      display: -webkit-box; -webkit-line-clamp: 2;
      -webkit-box-orient: vertical; overflow: hidden;
  }}
  .video-card-meta {{ font-size: 11px; color: {MUTED}; font-family: 'JetBrains Mono', monospace; }}

  .player-wrap {{
      background: #000; border-radius: 16px; overflow: hidden;
      aspect-ratio: 16/9; width: 100%;
      box-shadow: 0 20px 60px rgba(0,0,0,0.6);
  }}
  .player-wrap iframe {{ width:100%; height:100%; border:none; display:block; }}

  /* Theater mode full-width player */
  .player-wrap-theater {{
      background: #000; border-radius: 0; overflow: hidden;
      aspect-ratio: 16/9; width: 100%;
      box-shadow: 0 20px 60px rgba(0,0,0,0.8);
  }}
  .player-wrap-theater iframe {{ width:100%; height:100%; border:none; display:block; }}

  /* Mini player fixed bottom-right */
  .mini-player-container {{
      position: fixed; bottom: 24px; right: 24px;
      width: 320px; z-index: 9999;
      background: #000; border-radius: 12px; overflow: hidden;
      box-shadow: 0 8px 32px rgba(0,0,0,0.8);
      border: 1px solid {BORDER2};
  }}
  .mini-player-container iframe {{ width:100%; height:180px; border:none; display:block; }}
  .mini-player-bar {{
      background: {CARD_BG}; padding: 6px 10px;
      font-size: 11px; color: {MUTED2}; font-family: 'JetBrains Mono', monospace;
      white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  }}

  /* Share panel */
  .share-panel {{
      background: {CARD_BG}; border: 1px solid {BORDER};
      border-radius: 12px; padding: 16px; margin-top: 12px;
  }}
  .share-link-box {{
      background: {INPUT_BG}; border: 1px solid {BORDER2};
      border-radius: 8px; padding: 8px 12px;
      font-family: 'JetBrains Mono', monospace; font-size: 12px;
      color: {TEXT}; word-break: break-all; margin-bottom: 10px;
  }}
  .embed-code-box {{
      background: {INPUT_BG}; border: 1px solid {BORDER2};
      border-radius: 8px; padding: 10px 12px;
      font-family: 'JetBrains Mono', monospace; font-size: 11px;
      color: {MUTED2}; white-space: pre-wrap; word-break: break-all;
      margin-bottom: 10px; max-height: 100px; overflow-y: auto;
  }}

  .pill {{
      display: inline-block; background: {PILL_BG};
      border: 1px solid {BORDER2}; border-radius: 20px;
      padding: 3px 10px; font-size: 11px; color: {PILL_TXT};
      font-family: 'JetBrains Mono', monospace; margin-right: 6px;
  }}

  .queue-item {{
      background: {CARD_BG}; border: 1px solid {BORDER};
      border-radius: 8px; padding: 8px 10px; margin-bottom: 6px;
      font-size: 12px; color: {TEXT};
  }}
  .queue-item.active {{
      border-color: {ACCENT}; background: {PILL_BG};
  }}

  h1 {{ font-family:'Space Grotesk',sans-serif !important; font-weight:700 !important; }}
  h2,h3 {{ font-family:'Space Grotesk',sans-serif !important; font-weight:600 !important; }}

  #MainMenu, footer, header {{ visibility: hidden; }}
  .block-container {{ padding-top: 1.5rem !important; }}

  /* Keyboard shortcut hint badge */
  .kbd {{
      display: inline-block; background: {PILL_BG};
      border: 1px solid {BORDER2}; border-radius: 4px;
      padding: 1px 6px; font-size: 10px;
      font-family: 'JetBrains Mono', monospace; color: {PILL_TXT};
  }}

  /* Responsive grid — 2 cols on narrow viewports */
  @media (max-width: 768px) {{
      .mini-player-container {{ width: 220px; }}
      .mini-player-container iframe {{ height: 124px; }}
  }}
</style>
""", unsafe_allow_html=True)

# ─── Keyboard Shortcut JS ─────────────────────────────────────────────────────
# We inject a postMessage bridge — Streamlit can't receive JS events natively,
# but we can control the embedded iframe's player via the YouTube IFrame API.
st.markdown("""
<script>
(function() {
  // Wait for YouTube iframe to be ready
  function getPlayer() {
    return document.querySelector('.player-wrap iframe, .player-wrap-theater iframe');
  }
  document.addEventListener('keydown', function(e) {
    // Ignore if typing in an input
    if (['INPUT','TEXTAREA','SELECT'].includes(document.activeElement.tagName)) return;
    var iframe = getPlayer();
    if (!iframe) return;
    if (e.code === 'Space') {
      e.preventDefault();
      iframe.contentWindow.postMessage('{"event":"command","func":"pauseVideo","args":""}','*');
      // Toggle: try play first, player handles it
      setTimeout(function(){
        iframe.contentWindow.postMessage('{"event":"command","func":"playVideo","args":""}','*');
      }, 50);
    }
    if (e.code === 'ArrowRight') {
      iframe.contentWindow.postMessage('{"event":"command","func":"seekTo","args":[0,true]}','*');
    }
    if (e.code === 'KeyM') {
      iframe.contentWindow.postMessage('{"event":"command","func":"mute","args":""}','*');
    }
  });
})();
</script>
""", unsafe_allow_html=True)


# ─── Helpers ─────────────────────────────────────────────────────────────────
def extract_video_id(url_or_id: str) -> str | None:
    url_or_id = url_or_id.strip()
    if re.match(r'^[A-Za-z0-9_-]{11}$', url_or_id):
        return url_or_id
    m = re.search(r'youtu\.be/([A-Za-z0-9_-]{11})', url_or_id)
    if m: return m.group(1)
    m = re.search(r'[?&]v=([A-Za-z0-9_-]{11})', url_or_id)
    if m: return m.group(1)
    m = re.search(r'embed/([A-Za-z0-9_-]{11})', url_or_id)
    if m: return m.group(1)
    return None


def oembed_title(video_id: str) -> str | None:
    """Fetch video title via YouTube oEmbed — no API key needed."""
    try:
        url = f"https://www.youtube.com/oembed?url=https://youtu.be/{video_id}&format=json"
        r = requests.get(url, timeout=5)
        if r.status_code == 200:
            return r.json().get("title")
    except Exception:
        pass
    return None


def parse_bulk_urls(text: str) -> list[tuple[str, str]]:
    """Extract all YouTube video IDs from a multi-line paste. Returns (id, title) pairs."""
    lines = [l.strip() for l in text.strip().splitlines() if l.strip()]
    results = []
    for line in lines:
        vid = extract_video_id(line)
        if vid:
            title = oembed_title(vid) or vid
            results.append((vid, title))
    return results


def search_youtube(query: str, api_key: str, max_results: int = 12):
    url = "https://www.googleapis.com/youtube/v3/search"
    params = {"part": "snippet", "q": query, "type": "video",
              "maxResults": max_results, "key": api_key}
    try:
        r = requests.get(url, params=params, timeout=8)
        if r.status_code == 403:
            return None, "❌ API key error or quota exceeded."
        if r.status_code != 200:
            return None, f"❌ API error {r.status_code}"
        return r.json().get("items", []), None
    except Exception as e:
        return None, f"❌ Request failed: {e}"


def get_video_info(video_id: str, api_key: str):
    url = "https://www.googleapis.com/youtube/v3/videos"
    params = {"part": "snippet,statistics", "id": video_id, "key": api_key}
    try:
        r = requests.get(url, params=params, timeout=8)
        if r.status_code != 200: return None
        items = r.json().get("items", [])
        return items[0] if items else None
    except Exception:
        return None


def embed_html(video_id: str, autoplay: bool = True, theater: bool = False) -> str:
    params = urllib.parse.urlencode({
        "autoplay": int(autoplay), "rel": 0,
        "modestbranding": 1, "enablejsapi": 1,
    })
    cls = "player-wrap-theater" if theater else "player-wrap"
    return f"""
    <div class="{cls}">
      <iframe
        src="https://www.youtube.com/embed/{video_id}?{params}"
        allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
        allowfullscreen
      ></iframe>
    </div>"""


def mini_player_html(video_id: str, title: str) -> str:
    params = urllib.parse.urlencode({"autoplay": 0, "rel": 0, "modestbranding": 1})
    short = title[:40] + "…" if len(title) > 40 else title
    return f"""
    <div class="mini-player-container">
      <iframe src="https://www.youtube.com/embed/{video_id}?{params}"
        allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
        allowfullscreen></iframe>
      <div class="mini-player-bar">▶ {short}</div>
    </div>"""


def share_links_html(video_id: str, title: str) -> str:
    yt_url   = f"https://youtu.be/{video_id}"
    wa_url   = "https://api.whatsapp.com/send?text=" + urllib.parse.quote(f"{title} {yt_url}")
    tg_url   = "https://t.me/share/url?url=" + urllib.parse.quote(yt_url) + "&text=" + urllib.parse.quote(title)
    embed_code = (
        f'<iframe width="560" height="315" '
        f'src="https://www.youtube.com/embed/{video_id}" '
        f'frameborder="0" allowfullscreen></iframe>'
    )
    return yt_url, wa_url, tg_url, embed_code


def fmt_count(n):
    n = int(n)
    if n >= 1_000_000: return f"{n/1_000_000:.1f}M"
    if n >= 1_000:     return f"{n/1_000:.0f}K"
    return str(n)


# ─── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## ▶️ TubePlay")
    st.markdown(f"<p style='color:{MUTED};font-size:13px;margin-top:-8px'>YouTube player for your site</p>", unsafe_allow_html=True)

    # Theme toggle
    col_theme, col_theater, col_mini = st.columns(3)
    with col_theme:
        if st.button("🌙" if st.session_state.dark_mode else "☀️", use_container_width=True, help="Toggle theme"):
            st.session_state.dark_mode = not st.session_state.dark_mode
            st.rerun()
    with col_theater:
        if st.button("🎬", use_container_width=True, help="Theater mode"):
            st.session_state.theater_mode = not st.session_state.theater_mode
            st.rerun()
    with col_mini:
        if st.button("📺", use_container_width=True, help="Mini player"):
            st.session_state.mini_player = not st.session_state.mini_player
            st.rerun()

    st.markdown(f"<p style='font-size:11px;color:{MUTED};text-align:center;margin-top:2px'>"
                f"{'🌙 Dark' if st.session_state.dark_mode else '☀️ Light'} &nbsp;|&nbsp; "
                f"{'🎬 Theater ON' if st.session_state.theater_mode else 'Theater OFF'} &nbsp;|&nbsp; "
                f"{'📺 Mini ON' if st.session_state.mini_player else 'Mini OFF'}</p>",
                unsafe_allow_html=True)
    st.divider()

    st.markdown("#### 🔑 API Key")
    st.markdown(f"<p style='color:{MUTED};font-size:12px'>Free: <a href='https://console.developers.google.com' style='color:{ACCENT}'>console.developers.google.com</a><br>Enable <b>YouTube Data API v3</b></p>", unsafe_allow_html=True)
    api_key = st.text_input("YouTube Data API v3 key", type="password", placeholder="AIza...", key="api_key_input")
    st.divider()

    # ── Play by URL / ID ──
    st.markdown("#### 🔗 Play by URL / ID")
    direct_url = st.text_input("YouTube URL or Video ID", placeholder="https://youtu.be/... or dQw4w9WgXcQ", key="direct_url")
    col_a, col_b = st.columns([1, 1])
    with col_a:
        if st.button("▶ Play", use_container_width=True):
            vid = extract_video_id(direct_url)
            if vid:
                title = oembed_title(vid) or vid
                if api_key:
                    info = get_video_info(vid, api_key)
                    if info: title = info["snippet"]["title"]
                st.session_state.playing_id = vid
                st.session_state.playing_title = title
                if vid not in [h[0] for h in st.session_state.history]:
                    st.session_state.history.insert(0, (vid, title))
                    st.session_state.history = st.session_state.history[:10]
                st.rerun()
            else:
                st.error("Invalid URL/ID")
    with col_b:
        if st.button("+ Queue", use_container_width=True):
            vid = extract_video_id(direct_url)
            if vid:
                title = oembed_title(vid) or vid
                st.session_state.queue.append((vid, title))
                st.success(f"Added to queue")
            else:
                st.error("Invalid URL/ID")

    st.divider()

    # ── Bulk URL paste ──
    st.markdown("#### 📋 Bulk Add to Queue")
    bulk_text = st.text_area("Paste multiple YouTube URLs (one per line)", height=90, placeholder="https://youtu.be/abc\nhttps://youtu.be/xyz\n...", key="bulk_urls")
    if st.button("Add All to Queue", use_container_width=True):
        added = parse_bulk_urls(bulk_text)
        if added:
            for item in added:
                if item[0] not in [q[0] for q in st.session_state.queue]:
                    st.session_state.queue.append(item)
            st.success(f"Added {len(added)} video(s) to queue")
            st.rerun()
        else:
            st.error("No valid YouTube URLs found")

    st.divider()

    # ── Queue ──
    if st.session_state.queue:
        st.markdown("#### 🎵 Queue")
        for i, (qid, qtitle) in enumerate(st.session_state.queue):
            is_active = qid == st.session_state.playing_id
            label = f"{'▶ ' if is_active else f'{i+1}. '}{qtitle[:28]}{'…' if len(qtitle)>28 else ''}"
            if st.button(label, key=f"q_{i}_{qid}", use_container_width=True):
                st.session_state.playing_id = qid
                st.session_state.playing_title = qtitle
                st.session_state.queue_index = i
                st.rerun()
        col_prev, col_next, col_clr = st.columns(3)
        with col_prev:
            if st.button("⏮", use_container_width=True):
                if st.session_state.queue_index > 0:
                    st.session_state.queue_index -= 1
                    vid, title = st.session_state.queue[st.session_state.queue_index]
                    st.session_state.playing_id = vid
                    st.session_state.playing_title = title
                    st.rerun()
        with col_next:
            if st.button("⏭", use_container_width=True):
                if st.session_state.queue_index < len(st.session_state.queue) - 1:
                    st.session_state.queue_index += 1
                    vid, title = st.session_state.queue[st.session_state.queue_index]
                    st.session_state.playing_id = vid
                    st.session_state.playing_title = title
                    st.rerun()
        with col_clr:
            if st.button("🗑", use_container_width=True):
                st.session_state.queue = []
                st.session_state.queue_index = 0
                st.rerun()
        st.divider()

    # ── Watch history ──
    if st.session_state.history:
        st.markdown("#### 🕒 Recent")
        for vid_id, title in st.session_state.history[:5]:
            lbl = ("▶ " if vid_id == st.session_state.playing_id else "") + (title[:28] + "…" if len(title) > 28 else title)
            if st.button(lbl, key=f"hist_{vid_id}", use_container_width=True):
                st.session_state.playing_id = vid_id
                st.session_state.playing_title = title
                st.rerun()

    # ── Keyboard shortcuts hint ──
    st.divider()
    st.markdown(f"""
    <p style='font-size:11px;color:{MUTED}'>
      <b>Keyboard shortcuts</b><br>
      <span class='kbd'>Space</span> Play/Pause &nbsp;
      <span class='kbd'>M</span> Mute
    </p>
    """, unsafe_allow_html=True)


# ─── Main Content ─────────────────────────────────────────────────────────────
st.markdown("## In-Site YouTube Player")

# Mini player (fixed overlay, shown while browsing)
if st.session_state.mini_player and st.session_state.playing_id and not st.session_state.theater_mode:
    st.markdown(mini_player_html(st.session_state.playing_id, st.session_state.playing_title),
                unsafe_allow_html=True)

# ── Player Section ──
if st.session_state.playing_id:
    vid = st.session_state.playing_id

    if st.session_state.theater_mode:
        # Full-width theater layout
        st.markdown(embed_html(vid, theater=True), unsafe_allow_html=True)
        st.markdown(f"<p style='font-size:15px;font-weight:600;margin:12px 0 4px;color:{TEXT}'>{st.session_state.playing_title}</p>", unsafe_allow_html=True)

        info_col, share_col = st.columns([2, 1])
        with info_col:
            if api_key:
                info = get_video_info(vid, api_key)
                if info:
                    stats = info.get("statistics", {})
                    snip  = info["snippet"]
                    st.markdown(f"""
                    <div class="pill">👁 {fmt_count(stats.get('viewCount','0'))}</div>
                    <div class="pill">👍 {fmt_count(stats.get('likeCount','0'))}</div>
                    <p style="font-size:12px;color:{MUTED2};margin-top:8px">{snip.get('channelTitle','')}</p>
                    <p style="font-size:12px;color:{MUTED};line-height:1.5">{snip.get('description','')[:300]}{"…" if len(snip.get('description',''))>300 else ""}</p>
                    """, unsafe_allow_html=True)
        with share_col:
            _render_share = True
    else:
        # Normal 3:1 split layout
        col_player, col_info = st.columns([3, 1])
        with col_player:
            st.markdown(embed_html(vid), unsafe_allow_html=True)
        with col_info:
            st.markdown(f"**{st.session_state.playing_title}**")
            if api_key:
                info = get_video_info(vid, api_key)
                if info:
                    snip  = info["snippet"]
                    stats = info.get("statistics", {})
                    st.markdown(f"""
                    <div class="pill">👁 {fmt_count(stats.get('viewCount','0'))}</div>
                    <div class="pill">👍 {fmt_count(stats.get('likeCount','0'))}</div>
                    <br><br>
                    <p style="font-size:12px;color:{MUTED2};">{snip.get('channelTitle','')}</p>
                    <p style="font-size:12px;color:{MUTED};line-height:1.5">{snip.get('description','')[:280]}{"…" if len(snip.get('description',''))>280 else ""}</p>
                    """, unsafe_allow_html=True)
            st.markdown(f'<p style="font-size:12px;color:#555;margin-top:12px"><a href="https://youtu.be/{vid}" style="color:{ACCENT}" target="_blank">↗ Open on YouTube</a></p>', unsafe_allow_html=True)
            _render_share = True

    # ── Share Panel ──
    if _render_share:
        with st.expander("🔗 Share & Embed"):
            yt_url, wa_url, tg_url, embed_code = share_links_html(vid, st.session_state.playing_title)

            st.markdown(f"<p style='font-size:13px;font-weight:600;color:{TEXT}'>Shareable link</p>", unsafe_allow_html=True)
            st.markdown(f'<div class="share-link-box">{yt_url}</div>', unsafe_allow_html=True)
            st.code(yt_url, language=None)

            sc1, sc2 = st.columns(2)
            with sc1:
                st.markdown(f'<a href="{wa_url}" target="_blank" style="display:block;background:#25d366;color:#fff;text-align:center;padding:8px 0;border-radius:8px;text-decoration:none;font-weight:600;font-size:13px;">📱 Share on WhatsApp</a>', unsafe_allow_html=True)
            with sc2:
                st.markdown(f'<a href="{tg_url}" target="_blank" style="display:block;background:#229ed9;color:#fff;text-align:center;padding:8px 0;border-radius:8px;text-decoration:none;font-weight:600;font-size:13px;">✈️ Share on Telegram</a>', unsafe_allow_html=True)

            st.markdown(f"<p style='font-size:13px;font-weight:600;color:{TEXT};margin-top:12px'>Embed code</p>", unsafe_allow_html=True)
            st.code(embed_code, language="html")

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
        query = st.text_input("Search query", placeholder="lo-fi hip hop, coding music, tutorials…",
                              label_visibility="collapsed", key="search_query")
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
        st.markdown(f"<p style='color:{MUTED};font-size:13px'>Showing {len(st.session_state.search_results)} results — click ▶ to play or + to queue</p>", unsafe_allow_html=True)

        # Responsive: 4 cols on wide, 2 on narrow
        n_cols = 4
        cols = st.columns(n_cols)
        for i, item in enumerate(st.session_state.search_results):
            vid_id = item["id"]["videoId"]
            snip   = item["snippet"]
            thumb  = snip["thumbnails"].get("medium", snip["thumbnails"].get("default", {})).get("url", "")
            title  = snip.get("title", "Untitled")
            channel = snip.get("channelTitle", "")

            with cols[i % n_cols]:
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

                short = title[:22] + "…" if len(title) > 22 else title
                pb1, pb2 = st.columns([3, 1])
                with pb1:
                    if st.button(f"▶ {short}", key=f"play_{vid_id}", use_container_width=True):
                        st.session_state.playing_id = vid_id
                        st.session_state.playing_title = title
                        if vid_id not in [h[0] for h in st.session_state.history]:
                            st.session_state.history.insert(0, (vid_id, title))
                            st.session_state.history = st.session_state.history[:10]
                        st.rerun()
                with pb2:
                    if st.button("+", key=f"queue_{vid_id}", use_container_width=True, help="Add to queue"):
                        if vid_id not in [q[0] for q in st.session_state.queue]:
                            st.session_state.queue.append((vid_id, title))
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

**New: Play without an API key** — just paste any YouTube URL and we fetch the title via oEmbed (free, no key needed). Bulk-paste multiple URLs to build a queue instantly!
    """)
