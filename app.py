import streamlit as st
import requests
import re
import urllib.parse
import json
import io
import csv
import base64
import qrcode
from PIL import Image

# ─── Page Config ────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="TubePlay — In-Site YouTube Player",
    page_icon="▶️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── Session State Init ───────────────────────────────────────────────────────
DEFAULTS = {
    "playing_id": None,
    "playing_title": "",
    "search_results": [],
    "history": [],
    "queue": [],
    "queue_index": 0,
    "theater_mode": False,
    "dark_mode": True,
    "mini_player": False,
    # new
    "loop_mode": False,
    "shuffle_mode": False,
    "autoplay_next": True,
    "playback_speed": 1.0,
    "volume": 100,
    "font_size": "medium",
    "accent_color": "#6c63ff",
    "pinned_video": None,   # (vid_id, title)
    "video_notes": {},      # vid_id -> note text
    "short_url_cache": {},  # vid_id -> short url
    # NEW
    "favorites": [],        # list of (vid_id, title)
    "sleep_timer_mins": 0,  # 0 = off
    "sleep_timer_start": None,
    "watch_count": 0,       # total videos watched this session
    "search_order": "relevance",
    "search_type": "video",
    "search_safe": False,
}
for k, v in DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ─── Theme ─────────────────────────────────────────────────────────────────────
ACCENT     = st.session_state.accent_color
ACCENT_HOV = ACCENT  # slightly darker handled via CSS filter

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

FONT_SIZES = {"small": ("12px", "11px", "10px"), "medium": ("14px", "13px", "11px"), "large": ("16px", "15px", "13px")}
FS_BODY, FS_META, FS_SMALL = FONT_SIZES[st.session_state.font_size]

# ─── CSS ──────────────────────────────────────────────────────────────────────
st.markdown(f"""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;700&family=JetBrains+Mono:wght@400;500&display=swap');

  html, body, [data-testid="stApp"] {{
      background: {BG} !important;
      color: {TEXT};
      font-family: 'Space Grotesk', sans-serif;
      font-size: {FS_BODY};
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
      box-shadow: 0 0 0 2px {ACCENT}40 !important;
  }}

  .stButton > button {{
      background: {ACCENT} !important;
      color: #fff !important;
      border: none !important;
      border-radius: 8px !important;
      font-family: 'Space Grotesk', sans-serif !important;
      font-weight: 600 !important;
      font-size: {FS_BODY} !important;
      padding: 10px 22px !important;
      transition: filter 0.2s, transform 0.1s !important;
  }}
  .stButton > button:hover {{
      filter: brightness(0.88) !important;
      transform: translateY(-1px) !important;
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
      box-shadow: 0 8px 24px {ACCENT}26;
  }}
  .video-card img {{ width: 100%; display: block; }}
  .video-card-body {{ padding: 10px 12px 12px; }}
  .video-card-title {{
      font-size: {FS_META}; font-weight: 600;
      color: {TEXT}; line-height: 1.4; margin: 0 0 4px;
      display: -webkit-box; -webkit-line-clamp: 2;
      -webkit-box-orient: vertical; overflow: hidden;
  }}
  .video-card-meta {{ font-size: {FS_SMALL}; color: {MUTED}; font-family: 'JetBrains Mono', monospace; }}

  .player-wrap {{
      background: #000; border-radius: 16px; overflow: hidden;
      aspect-ratio: 16/9; width: 100%;
      box-shadow: 0 20px 60px rgba(0,0,0,0.6);
  }}
  .player-wrap iframe {{ width:100%; height:100%; border:none; display:block; }}
  .player-wrap-theater {{
      background: #000; border-radius: 0; overflow: hidden;
      aspect-ratio: 16/9; width: 100%;
      box-shadow: 0 20px 60px rgba(0,0,0,0.8);
  }}
  .player-wrap-theater iframe {{ width:100%; height:100%; border:none; display:block; }}

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
      font-size: {FS_SMALL}; color: {MUTED2}; font-family: 'JetBrains Mono', monospace;
      white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  }}

  .pill {{
      display: inline-block; background: {PILL_BG};
      border: 1px solid {BORDER2}; border-radius: 20px;
      padding: 3px 10px; font-size: {FS_SMALL}; color: {PILL_TXT};
      font-family: 'JetBrains Mono', monospace; margin-right: 6px;
  }}
  .pill-accent {{
      display: inline-block; background: {ACCENT}22;
      border: 1px solid {ACCENT}55; border-radius: 20px;
      padding: 3px 10px; font-size: {FS_SMALL}; color: {ACCENT};
      font-family: 'JetBrains Mono', monospace; margin-right: 6px;
  }}

  /* Like/dislike ratio bar */
  .ratio-bar-wrap {{
      margin: 8px 0 4px;
  }}
  .ratio-bar-bg {{
      height: 6px; background: {BORDER2}; border-radius: 3px; overflow: hidden;
  }}
  .ratio-bar-fill {{
      height: 100%; background: {ACCENT}; border-radius: 3px;
      transition: width 0.5s ease;
  }}
  .ratio-labels {{
      display: flex; justify-content: space-between;
      font-size: {FS_SMALL}; color: {MUTED}; font-family: 'JetBrains Mono', monospace;
      margin-top: 3px;
  }}

  /* Pinned video banner */
  .pinned-banner {{
      background: {ACCENT}15; border: 1px solid {ACCENT}40;
      border-radius: 10px; padding: 10px 14px; margin-bottom: 14px;
      display: flex; align-items: center; gap: 10px;
  }}
  .pinned-banner-text {{
      font-size: {FS_META}; color: {TEXT};
  }}
  .pinned-badge {{
      font-size: {FS_SMALL}; color: {ACCENT};
      font-family: 'JetBrains Mono', monospace;
      background: {ACCENT}20; padding: 2px 8px; border-radius: 12px;
  }}

  /* Notes box */
  .notes-box {{
      background: {INPUT_BG}; border: 1px solid {BORDER2};
      border-radius: 8px; padding: 10px 12px; margin-top: 6px;
      font-size: {FS_META}; color: {MUTED2}; font-family: 'JetBrains Mono', monospace;
      white-space: pre-wrap; line-height: 1.5;
  }}

  .queue-item {{
      background: {CARD_BG}; border: 1px solid {BORDER};
      border-radius: 8px; padding: 8px 10px; margin-bottom: 6px;
      font-size: {FS_META}; color: {TEXT};
  }}
  .queue-item.active {{ border-color: {ACCENT}; background: {PILL_BG}; }}

  .share-link-box {{
      background: {INPUT_BG}; border: 1px solid {BORDER2};
      border-radius: 8px; padding: 8px 12px;
      font-family: 'JetBrains Mono', monospace; font-size: 12px;
      color: {TEXT}; word-break: break-all; margin-bottom: 10px;
  }}

  /* Welcome grid */
  .welcome-hero {{
      text-align: center; padding: 40px 20px 20px;
  }}
  .welcome-hero h2 {{
      font-size: 2em; font-weight: 700; color: {TEXT}; margin-bottom: 8px;
  }}
  .welcome-hero p {{
      font-size: {FS_BODY}; color: {MUTED}; margin-bottom: 24px;
  }}

  h1 {{ font-family:'Space Grotesk',sans-serif !important; font-weight:700 !important; }}
  h2,h3 {{ font-family:'Space Grotesk',sans-serif !important; font-weight:600 !important; }}
  #MainMenu, footer, header {{ visibility: hidden; }}
  .block-container {{ padding-top: 1.5rem !important; }}

  .kbd {{
      display: inline-block; background: {PILL_BG};
      border: 1px solid {BORDER2}; border-radius: 4px;
      padding: 1px 6px; font-size: 10px;
      font-family: 'JetBrains Mono', monospace; color: {PILL_TXT};
  }}

  /* Favorites star glow */
  .fav-star {{
      cursor: pointer; font-size: 1.1em;
      transition: transform 0.2s, filter 0.2s;
  }}
  .fav-star:hover {{ transform: scale(1.3); filter: drop-shadow(0 0 4px gold); }}

  /* Sleep timer badge */
  .sleep-badge {{
      display: inline-flex; align-items: center; gap: 5px;
      background: #ff6b6b22; border: 1px solid #ff6b6b55;
      border-radius: 20px; padding: 3px 10px;
      font-size: {FS_SMALL}; color: #ff6b6b;
      font-family: 'JetBrains Mono', monospace;
  }}

  /* Stats bar */
  .stats-bar {{
      display: flex; gap: 12px; flex-wrap: wrap;
      background: {CARD_BG}; border: 1px solid {BORDER};
      border-radius: 10px; padding: 10px 14px; margin-bottom: 14px;
  }}
  .stat-item {{
      font-size: {FS_SMALL}; color: {MUTED2};
      font-family: 'JetBrains Mono', monospace;
  }}
  .stat-item span {{ color: {ACCENT}; font-weight: 700; }}

  @media (max-width: 768px) {{
      .mini-player-container {{ width: 220px; }}
      .mini-player-container iframe {{ height: 124px; }}
  }}
</style>
""", unsafe_allow_html=True)

# ─── JS: Keyboard shortcuts + Clipboard helper ──────────────────────────────
st.markdown("""
<script>
(function() {
  function getPlayer() {
    return document.querySelector('.player-wrap iframe, .player-wrap-theater iframe');
  }
  document.addEventListener('keydown', function(e) {
    if (['INPUT','TEXTAREA','SELECT'].includes(document.activeElement.tagName)) return;
    var iframe = getPlayer();
    if (!iframe) return;
    if (e.code === 'Space') {
      e.preventDefault();
      iframe.contentWindow.postMessage('{"event":"command","func":"pauseVideo","args":""}','*');
      setTimeout(function(){
        iframe.contentWindow.postMessage('{"event":"command","func":"playVideo","args":""}','*');
      }, 50);
    }
    if (e.code === 'KeyM') {
      iframe.contentWindow.postMessage('{"event":"command","func":"mute","args":""}','*');
    }
    if (e.code === 'KeyF') {
      var wrap = document.querySelector('.player-wrap, .player-wrap-theater');
      if (wrap && wrap.requestFullscreen) wrap.requestFullscreen();
    }
    if (e.code === 'KeyP') {
      var iframe2 = getPlayer();
      if (iframe2 && document.pictureInPictureEnabled) {
        // PiP on iframes works via the video element inside
        try { iframe2.contentWindow.document.querySelector('video').requestPictureInPicture(); } catch(err) {}
      }
    }
  });
  // Clipboard copy helper
  window.copyToClipboard = function(text) {
    navigator.clipboard.writeText(text).then(function(){
      var el = document.getElementById('copy-toast');
      if (el) { el.style.opacity='1'; setTimeout(function(){ el.style.opacity='0'; }, 1800); }
    });
  };
})();
</script>
<div id="copy-toast" style="
  position:fixed;bottom:80px;right:24px;z-index:99999;
  background:#222;color:#fff;padding:8px 18px;border-radius:8px;
  font-size:13px;opacity:0;transition:opacity 0.3s;pointer-events:none;
">✓ Copied to clipboard</div>
""", unsafe_allow_html=True)


# ─── Helpers ──────────────────────────────────────────────────────────────────
def extract_video_id(url_or_id: str):
    url_or_id = url_or_id.strip()
    # handle ?t= timestamp
    start_t = 0
    t_match = re.search(r'[?&]t=(\d+)', url_or_id)
    if t_match:
        start_t = int(t_match.group(1))
    if re.match(r'^[A-Za-z0-9_-]{11}$', url_or_id):
        return url_or_id, 0
    m = re.search(r'youtu\.be/([A-Za-z0-9_-]{11})', url_or_id)
    if m: return m.group(1), start_t
    m = re.search(r'[?&]v=([A-Za-z0-9_-]{11})', url_or_id)
    if m: return m.group(1), start_t
    m = re.search(r'embed/([A-Za-z0-9_-]{11})', url_or_id)
    if m: return m.group(1), start_t
    return None, 0

def oembed_title(video_id: str):
    try:
        r = requests.get(f"https://www.youtube.com/oembed?url=https://youtu.be/{video_id}&format=json", timeout=5)
        if r.status_code == 200:
            return r.json().get("title")
    except Exception:
        pass
    return None

def parse_bulk_urls(text: str):
    lines = [l.strip() for l in text.strip().splitlines() if l.strip()]
    results = []
    for line in lines:
        vid, _ = extract_video_id(line)
        if vid:
            title = oembed_title(vid) or vid
            results.append((vid, title))
    return results

def search_youtube(query: str, api_key: str, max_results: int = 12,
                   order: str = "relevance", video_type: str = "video", safe: bool = False):
    url = "https://www.googleapis.com/youtube/v3/search"
    params = {"part": "snippet", "q": query, "type": video_type,
              "maxResults": max_results, "key": api_key,
              "order": order,
              "safeSearch": "strict" if safe else "none"}
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

def embed_html(video_id: str, autoplay: bool = True, theater: bool = False,
               speed: float = 1.0, volume: int = 100, start: int = 0, loop: bool = False) -> str:
    params = urllib.parse.urlencode({
        "autoplay": int(autoplay), "rel": 0,
        "modestbranding": 1, "enablejsapi": 1,
        "start": start,
        "loop": int(loop),
        "playlist": video_id if loop else "",
    })
    cls = "player-wrap-theater" if theater else "player-wrap"
    yt_direct = f"https://www.youtube.com/watch?v={video_id}"
    # Speed/volume via postMessage; also detect embedding-blocked errors and show fallback
    speed_vol_js = f"""
<script>
(function() {{
  var cls = '{cls}';
  var vid = '{video_id}';
  var ytDirect = 'https://www.youtube.com/watch?v=' + vid;
  var attempts = 0;
  function trySetup() {{
    var iframe = document.querySelector('.' + cls + ' iframe');
    if (!iframe) {{ if (attempts++ < 20) setTimeout(trySetup, 500); return; }}
    iframe.addEventListener('load', function() {{
      setTimeout(function() {{
        iframe.contentWindow.postMessage(
          JSON.stringify({{event:'command',func:'setPlaybackRate',args:[{speed}]}}), '*');
        iframe.contentWindow.postMessage(
          JSON.stringify({{event:'command',func:'setVolume',args:[{volume}]}}), '*');
      }}, 1200);
    }});
  }}
  // YouTube iframe API error handler — error 150/101 = embedding not allowed
  window.addEventListener('message', function(e) {{
    if (!e.data) return;
    try {{
      var d = typeof e.data === 'string' ? JSON.parse(e.data) : e.data;
      if (d.event === 'infoDelivery' && d.info && d.info.playerState === 5) return;
      if (d.event === 'onError' && (d.info === 150 || d.info === 101 || d.info === 100)) {{
        var wrap = document.querySelector('.' + cls);
        if (wrap && !wrap.dataset.fallbackShown) {{
          wrap.dataset.fallbackShown = '1';
          wrap.innerHTML = '<div style="display:flex;flex-direction:column;align-items:center;justify-content:center;height:100%;background:#0d0d0f;border-radius:16px;padding:32px;text-align:center;gap:16px">'
            + '<div style="font-size:2.5em">🚫</div>'
            + '<div style="color:#e8e8e8;font-size:15px;font-weight:600">Embedding disabled for this video</div>'
            + '<div style="color:#888;font-size:13px">The uploader has restricted embedding on third-party sites.</div>'
            + '<a href="' + ytDirect + '" target="_blank" style="margin-top:8px;background:#ff0000;color:#fff;text-decoration:none;padding:10px 24px;border-radius:8px;font-weight:700;font-size:14px">▶ Watch on YouTube</a>'
            + '</div>';
        }}
      }}
    }} catch(err) {{}}
  }});
  trySetup();
}})();
</script>"""
    return f"""
    <div class="{cls}">
      <iframe
        src="https://www.youtube.com/embed/{video_id}?{params}"
        allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
        allowfullscreen
      ></iframe>
    </div>{speed_vol_js}"""

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

def share_links_html(video_id: str, title: str):
    yt_url    = f"https://youtu.be/{video_id}"
    wa_url    = "https://api.whatsapp.com/send?text=" + urllib.parse.quote(f"{title} {yt_url}")
    tg_url    = "https://t.me/share/url?url=" + urllib.parse.quote(yt_url) + "&text=" + urllib.parse.quote(title)
    tw_url    = "https://twitter.com/intent/tweet?url=" + urllib.parse.quote(yt_url) + "&text=" + urllib.parse.quote(title)
    embed_code = (f'<iframe width="560" height="315" '
                  f'src="https://www.youtube.com/embed/{video_id}" '
                  f'frameborder="0" allowfullscreen></iframe>')
    return yt_url, wa_url, tg_url, tw_url, embed_code

def get_short_url(video_id: str, yt_url: str) -> str:
    if video_id in st.session_state.short_url_cache:
        return st.session_state.short_url_cache[video_id]
    try:
        r = requests.get(f"https://tinyurl.com/api-create.php?url={urllib.parse.quote(yt_url)}", timeout=5)
        if r.status_code == 200:
            short = r.text.strip()
            st.session_state.short_url_cache[video_id] = short
            return short
    except Exception:
        pass
    return yt_url

def make_qr_b64(url: str) -> str:
    return base64.b64encode(make_qr_png(url)).decode()

def make_qr_png(url: str) -> bytes:
    qr = qrcode.QRCode(version=1, box_size=6, border=2,
                       error_correction=qrcode.constants.ERROR_CORRECT_M)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#111111", back_color="#ffffff")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()

def fmt_count(n):
    n = int(n)
    if n >= 1_000_000: return f"{n/1_000_000:.1f}M"
    if n >= 1_000:     return f"{n/1_000:.0f}K"
    return str(n)

def like_ratio_bar_html(stats: dict) -> str:
    likes    = int(stats.get("likeCount", 0))
    # YouTube removed public dislike counts; we show likes / views ratio instead
    views    = int(stats.get("viewCount", 1))
    ratio    = min(likes / max(views, 1) * 100 * 10, 100)  # scaled for visibility
    likes_fmt = fmt_count(likes)
    views_fmt = fmt_count(views)
    # Use inline styles only (no CSS classes) so this safely embeds inside other f-strings
    return (
        f'<div style="margin:8px 0 4px">'
        f'<div style="font-size:{FS_SMALL};color:{MUTED};margin-bottom:3px">👍 Engagement ratio</div>'
        f'<div style="height:6px;background:{BORDER2};border-radius:3px;overflow:hidden">'
        f'<div style="height:100%;width:{ratio:.1f}%;background:{ACCENT};border-radius:3px;transition:width 0.5s ease"></div>'
        f'</div>'
        f'<div style="display:flex;justify-content:space-between;font-size:{FS_SMALL};color:{MUTED};font-family:JetBrains Mono,monospace;margin-top:3px">'
        f'<span>👍 {likes_fmt}</span><span>👁 {views_fmt} views</span>'
        f'</div></div>'
    )

def export_queue_txt() -> bytes:
    lines = [f"https://youtu.be/{vid}  # {title}" for vid, title in st.session_state.queue]
    return "\n".join(lines).encode("utf-8")

def export_history_csv() -> bytes:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["Video ID", "Title", "URL"])
    for vid, title in st.session_state.history:
        w.writerow([vid, title, f"https://youtu.be/{vid}"])
    return buf.getvalue().encode("utf-8")

def play_video(vid_id: str, title: str):
    st.session_state.playing_id = vid_id
    st.session_state.playing_title = title
    st.session_state.scroll_to_player = True
    st.session_state.watch_count += 1
    if vid_id not in [h[0] for h in st.session_state.history]:
        st.session_state.history.insert(0, (vid_id, title))
        st.session_state.history = st.session_state.history[:20]

def toggle_favorite(vid_id: str, title: str):
    ids = [f[0] for f in st.session_state.favorites]
    if vid_id in ids:
        st.session_state.favorites = [f for f in st.session_state.favorites if f[0] != vid_id]
    else:
        st.session_state.favorites.insert(0, (vid_id, title))

def export_notes_txt() -> bytes:
    lines = []
    for vid_id, note in st.session_state.video_notes.items():
        url = f"https://youtu.be/{vid_id}"
        lines.append(f"=== {url} ===\n{note}\n")
    return "\n".join(lines).encode("utf-8") if lines else b"No notes yet."

def check_sleep_timer() -> bool:
    """Returns True if sleep timer has expired."""
    import time
    if st.session_state.sleep_timer_mins > 0 and st.session_state.sleep_timer_start:
        elapsed = time.time() - st.session_state.sleep_timer_start
        if elapsed >= st.session_state.sleep_timer_mins * 60:
            return True
    return False


# ─── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## ▶️ TubePlay")
    st.markdown(f"<p style='color:{MUTED};font-size:12px;margin-top:-8px'>YouTube player for your site</p>", unsafe_allow_html=True)

    # ── Top controls row ──
    col_t, col_th, col_mn = st.columns(3)
    with col_t:
        if st.button("🌙" if st.session_state.dark_mode else "☀️", use_container_width=True, help="Toggle theme"):
            st.session_state.dark_mode = not st.session_state.dark_mode; st.rerun()
    with col_th:
        if st.button("🎬", use_container_width=True, help="Theater mode"):
            st.session_state.theater_mode = not st.session_state.theater_mode; st.rerun()
    with col_mn:
        if st.button("📺", use_container_width=True, help="Mini player"):
            st.session_state.mini_player = not st.session_state.mini_player; st.rerun()

    st.divider()

    # ── Appearance ──
    with st.expander("🎨 Appearance"):
        new_accent = st.color_picker("Accent color", value=st.session_state.accent_color, key="accent_picker")
        if new_accent != st.session_state.accent_color:
            st.session_state.accent_color = new_accent; st.rerun()
        fs = st.radio("Font size", ["small", "medium", "large"],
                      index=["small","medium","large"].index(st.session_state.font_size),
                      horizontal=True, key="fs_radio")
        if fs != st.session_state.font_size:
            st.session_state.font_size = fs; st.rerun()

    # ── Playback settings ──
    with st.expander("⚙️ Playback"):
        spd = st.select_slider("Speed", options=[0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0],
                               value=st.session_state.playback_speed, key="speed_slider")
        if spd != st.session_state.playback_speed:
            st.session_state.playback_speed = spd; st.rerun()
        vol = st.slider("Volume", 0, 100, st.session_state.volume, key="vol_slider")
        if vol != st.session_state.volume:
            st.session_state.volume = vol; st.rerun()

        c1, c2, c3 = st.columns(3)
        with c1:
            loop = st.checkbox("🔁 Loop", value=st.session_state.loop_mode, key="loop_cb")
            if loop != st.session_state.loop_mode:
                st.session_state.loop_mode = loop
        with c2:
            shuffle = st.checkbox("🔀 Shuffle", value=st.session_state.shuffle_mode, key="shuf_cb")
            if shuffle != st.session_state.shuffle_mode:
                st.session_state.shuffle_mode = shuffle
        with c3:
            auto_n = st.checkbox("⏭ Auto", value=st.session_state.autoplay_next, key="auto_cb")
            if auto_n != st.session_state.autoplay_next:
                st.session_state.autoplay_next = auto_n

    st.divider()

    # ── API Key ──
    st.markdown("#### 🔑 API Key")
    api_key = st.text_input("YouTube Data API v3 key", type="password", placeholder="AIza…", key="api_key_input")
    st.divider()

    # ── Play by URL / ID ──
    st.markdown("#### 🔗 Play by URL / ID")
    direct_url = st.text_input("YouTube URL or Video ID", placeholder="https://youtu.be/… or dQw4w9WgXcQ", key="direct_url")
    col_a, col_b = st.columns([1, 1])
    with col_a:
        if st.button("▶ Play", use_container_width=True):
            vid, start_t = extract_video_id(direct_url)
            if vid:
                title = oembed_title(vid) or vid
                if api_key:
                    info = get_video_info(vid, api_key)
                    if info: title = info["snippet"]["title"]
                play_video(vid, title)
                st.session_state["start_t"] = start_t
                st.rerun()
            else:
                st.error("Invalid URL/ID")
    with col_b:
        if st.button("+ Queue", use_container_width=True):
            vid, _ = extract_video_id(direct_url)
            if vid:
                title = oembed_title(vid) or vid
                if (vid, title) not in st.session_state.queue:
                    st.session_state.queue.append((vid, title))
                st.success("Added to queue")
            else:
                st.error("Invalid URL/ID")

    st.divider()

    # ── Bulk Add ──
    st.markdown("#### 📋 Bulk Add to Queue")
    bulk_text = st.text_area("Paste multiple YouTube URLs (one per line)", height=80, placeholder="https://youtu.be/abc\nhttps://youtu.be/xyz", key="bulk_urls")
    if st.button("Add All to Queue", use_container_width=True):
        added = parse_bulk_urls(bulk_text)
        if added:
            existing_ids = [q[0] for q in st.session_state.queue]
            new = [x for x in added if x[0] not in existing_ids]
            st.session_state.queue.extend(new)
            st.success(f"Added {len(new)} video(s)")
            st.rerun()
        else:
            st.error("No valid URLs found")

    st.divider()

    # ── Queue ──
    if st.session_state.queue:
        st.markdown("#### 🎵 Queue")

        # Export queue
        st.download_button("⬇ Export queue.txt", data=export_queue_txt(),
                           file_name="tubeplay_queue.txt", mime="text/plain",
                           use_container_width=True)

        for i, (qid, qtitle) in enumerate(st.session_state.queue):
            is_active = qid == st.session_state.playing_id
            label = f"{'▶ ' if is_active else f'{i+1}. '}{qtitle[:26]}{'…' if len(qtitle)>26 else ''}"
            if st.button(label, key=f"q_{i}_{qid}", use_container_width=True):
                play_video(qid, qtitle)
                st.session_state.queue_index = i
                st.rerun()

        c_prev, c_next, c_shuf, c_clr = st.columns(4)
        with c_prev:
            if st.button("⏮", use_container_width=True):
                idx = max(st.session_state.queue_index - 1, 0)
                qid, qtitle = st.session_state.queue[idx]
                play_video(qid, qtitle); st.session_state.queue_index = idx; st.rerun()
        with c_next:
            if st.button("⏭", use_container_width=True):
                if st.session_state.shuffle_mode:
                    import random
                    idx = random.randint(0, len(st.session_state.queue)-1)
                else:
                    idx = min(st.session_state.queue_index + 1, len(st.session_state.queue)-1)
                qid, qtitle = st.session_state.queue[idx]
                play_video(qid, qtitle); st.session_state.queue_index = idx; st.rerun()
        with c_shuf:
            if st.button("🔀", use_container_width=True, help="Shuffle now"):
                import random
                random.shuffle(st.session_state.queue)
                st.rerun()
        with c_clr:
            if st.button("🗑", use_container_width=True):
                st.session_state.queue = []; st.session_state.queue_index = 0; st.rerun()

        st.divider()

    # ── Pinned Video ──
    if st.session_state.pinned_video:
        pvid, ptitle = st.session_state.pinned_video
        short_p = ptitle[:24] + "…" if len(ptitle) > 24 else ptitle
        st.markdown(f"#### 📌 Pinned")
        pc1, pc2 = st.columns([3, 1])
        with pc1:
            if st.button(f"▶ {short_p}", key="play_pinned", use_container_width=True):
                play_video(pvid, ptitle); st.rerun()
        with pc2:
            if st.button("✕", key="unpin", use_container_width=True):
                st.session_state.pinned_video = None; st.rerun()
        st.divider()

    # ── Favorites ──
    if st.session_state.favorites:
        st.markdown("#### ⭐ Favorites")
        for fav_id, fav_title in st.session_state.favorites[:8]:
            fl1, fl2 = st.columns([4, 1])
            with fl1:
                flbl = ("▶ " if fav_id == st.session_state.playing_id else "") + (fav_title[:22] + "…" if len(fav_title) > 22 else fav_title)
                if st.button(flbl, key=f"fav_play_{fav_id}", use_container_width=True):
                    play_video(fav_id, fav_title); st.rerun()
            with fl2:
                if st.button("✕", key=f"fav_rm_{fav_id}", use_container_width=True):
                    st.session_state.favorites = [f for f in st.session_state.favorites if f[0] != fav_id]; st.rerun()
        if st.session_state.video_notes:
            st.download_button("⬇ Export notes.txt", data=export_notes_txt(),
                               file_name="tubeplay_notes.txt", mime="text/plain",
                               use_container_width=True)
        st.divider()

    # ── Sleep Timer ──
    import time as _time
    with st.expander("😴 Sleep Timer"):
        sleep_mins = st.select_slider("Stop after (minutes)", options=[0, 5, 10, 15, 20, 30, 45, 60, 90, 120],
                                      value=st.session_state.sleep_timer_mins, key="sleep_slider")
        if sleep_mins != st.session_state.sleep_timer_mins:
            st.session_state.sleep_timer_mins = sleep_mins
            st.session_state.sleep_timer_start = _time.time() if sleep_mins > 0 else None
            st.rerun()
        if st.session_state.sleep_timer_mins > 0 and st.session_state.sleep_timer_start:
            elapsed = _time.time() - st.session_state.sleep_timer_start
            remaining = max(0, st.session_state.sleep_timer_mins * 60 - elapsed)
            rm, rs = int(remaining // 60), int(remaining % 60)
            st.markdown(f'<div class="sleep-badge">😴 Stops in {rm}m {rs:02d}s</div>', unsafe_allow_html=True)
            if remaining == 0:
                st.session_state.playing_id = None
                st.session_state.sleep_timer_mins = 0
                st.session_state.sleep_timer_start = None
                st.rerun()
        if st.session_state.sleep_timer_mins > 0:
            if st.button("Cancel timer", use_container_width=True):
                st.session_state.sleep_timer_mins = 0
                st.session_state.sleep_timer_start = None
                st.rerun()
    st.divider()

    # ── Watch history ──
    if st.session_state.history:
        st.markdown("#### 🕒 Recent")
        for vid_id, title in st.session_state.history[:6]:
            lbl = ("▶ " if vid_id == st.session_state.playing_id else "") + (title[:26] + "…" if len(title) > 26 else title)
            if st.button(lbl, key=f"hist_{vid_id}", use_container_width=True):
                play_video(vid_id, title); st.rerun()
        st.download_button("⬇ Export history.csv", data=export_history_csv(),
                           file_name="tubeplay_history.csv", mime="text/csv",
                           use_container_width=True)
        st.divider()

    # ── Keyboard hints ──
    st.markdown(f"""
    <p style='font-size:11px;color:{MUTED}'>
      <b>Keyboard</b><br>
      <span class='kbd'>Space</span> Play/Pause &nbsp;
      <span class='kbd'>M</span> Mute &nbsp;
      <span class='kbd'>F</span> Fullscreen &nbsp;
      <span class='kbd'>P</span> PiP
    </p>
    """, unsafe_allow_html=True)


# ─── Main Content ─────────────────────────────────────────────────────────────
st.markdown("## ▶️ TubePlay")

# ── Session Stats Bar ──
if st.session_state.watch_count > 0 or st.session_state.queue or st.session_state.favorites:
    fav_count = len(st.session_state.favorites)
    q_count = len(st.session_state.queue)
    h_count = len(st.session_state.history)
    st.markdown(f"""
    <div class="stats-bar">
      <div class="stat-item">🎬 Watched: <span>{st.session_state.watch_count}</span></div>
      <div class="stat-item">🎵 Queue: <span>{q_count}</span></div>
      <div class="stat-item">⭐ Favorites: <span>{fav_count}</span></div>
      <div class="stat-item">🕒 History: <span>{h_count}</span></div>
    </div>
    """, unsafe_allow_html=True)

# Mini player overlay
if st.session_state.mini_player and st.session_state.playing_id and not st.session_state.theater_mode:
    st.markdown(mini_player_html(st.session_state.playing_id, st.session_state.playing_title), unsafe_allow_html=True)

# ── Welcome screen (no video playing, no search results) ──
if not st.session_state.playing_id and not st.session_state.search_results:
    st.markdown(f"""
    <div class="welcome-hero">
      <div style="font-size:3em;margin-bottom:12px">▶️</div>
      <h2>Your in-site YouTube player</h2>
      <p>Paste a URL in the sidebar to start playing, or search below to discover videos.</p>
    </div>
    """, unsafe_allow_html=True)

    # Feature highlights
    fc1, fc2, fc3, fc4, fc5, fc6 = st.columns(6)
    features = [
        ("🎵", "Queue", "Build a playlist from any URLs"),
        ("🎬", "Theater", "Distraction-free full-width mode"),
        ("📺", "Mini Player", "Float the player while you browse"),
        ("🔀", "Shuffle", "Randomize your queue anytime"),
        ("⭐", "Favorites", "Star videos to revisit anytime"),
        ("😴", "Sleep Timer", "Auto-stop playback after a set time"),
    ]
    for col, (icon, title, desc) in zip([fc1, fc2, fc3, fc4, fc5, fc6], features):
        with col:
            st.markdown(f"""
            <div style="background:{CARD_BG};border:1px solid {BORDER};border-radius:12px;padding:16px 14px;text-align:center">
              <div style="font-size:1.8em">{icon}</div>
              <div style="font-weight:700;margin:6px 0 4px;font-size:{FS_BODY};color:{TEXT}">{title}</div>
              <div style="font-size:{FS_SMALL};color:{MUTED};line-height:1.4">{desc}</div>
            </div>
            """, unsafe_allow_html=True)
    st.markdown("")

# ── Pinned video banner ──
if st.session_state.pinned_video and st.session_state.playing_id != st.session_state.pinned_video[0]:
    pvid, ptitle = st.session_state.pinned_video
    st.markdown(f"""
    <div class="pinned-banner">
      <span style="font-size:1.2em">📌</span>
      <span class="pinned-badge">Pinned</span>
      <span class="pinned-banner-text">{ptitle[:60]}{"…" if len(ptitle)>60 else ""}</span>
    </div>
    """, unsafe_allow_html=True)

# ── Player ──
if st.session_state.playing_id:
    vid  = st.session_state.playing_id
    start_t = st.session_state.get("start_t", 0)
    _render_share = False
    st.markdown('<div id="tubeplay-player"></div>', unsafe_allow_html=True)
    if st.session_state.pop("scroll_to_player", False):
        st.markdown("""
        <script>
        setTimeout(function() {
          var player = window.parent.document.getElementById('tubeplay-player');
          if (player) player.scrollIntoView({behavior: 'smooth', block: 'start'});
        }, 120);
        </script>
        """, unsafe_allow_html=True)

    if st.session_state.theater_mode:
        st.markdown(embed_html(vid, theater=True,
                               speed=st.session_state.playback_speed,
                               volume=st.session_state.volume,
                               start=start_t,
                               loop=st.session_state.loop_mode), unsafe_allow_html=True)
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
                    {like_ratio_bar_html(stats)}
                    <p style="font-size:{FS_META};color:{MUTED2};margin-top:8px">{snip.get('channelTitle','')}</p>
                    <p style="font-size:{FS_META};color:{MUTED};line-height:1.5">{snip.get('description','')[:300]}{"…" if len(snip.get('description',''))>300 else ""}</p>
                    """, unsafe_allow_html=True)
        with share_col:
            _render_share = True
    else:
        col_player, col_info = st.columns([3, 1])
        with col_player:
            st.markdown(embed_html(vid,
                                   speed=st.session_state.playback_speed,
                                   volume=st.session_state.volume,
                                   start=start_t,
                                   loop=st.session_state.loop_mode), unsafe_allow_html=True)

            # Fullscreen + PiP buttons below player
            btn_fs, btn_pip, btn_pin, btn_fav, _ = st.columns([1, 1, 1, 1, 2])
            with btn_fs:
                st.markdown(f"""<button onclick="var w=document.querySelector('.player-wrap,.player-wrap-theater');if(w&&w.requestFullscreen)w.requestFullscreen();"
                  style="background:{ACCENT};color:#fff;border:none;border-radius:8px;padding:7px 14px;cursor:pointer;font-size:{FS_SMALL};font-weight:600">⛶ Fullscreen</button>""",
                  unsafe_allow_html=True)
            with btn_pip:
                st.markdown(f"""<button onclick="var v=document.querySelector('.player-wrap iframe');if(v)try{{v.contentWindow.document.querySelector('video').requestPictureInPicture();}}catch(e){{}}"
                  style="background:{CARD_BG};color:{TEXT};border:1px solid {BORDER2};border-radius:8px;padding:7px 14px;cursor:pointer;font-size:{FS_SMALL};font-weight:600">📺 PiP</button>""",
                  unsafe_allow_html=True)
            with btn_pin:
                pin_label = "📌 Unpin" if st.session_state.pinned_video and st.session_state.pinned_video[0] == vid else "📌 Pin"
                if st.button(pin_label, key="pin_btn"):
                    if st.session_state.pinned_video and st.session_state.pinned_video[0] == vid:
                        st.session_state.pinned_video = None
                    else:
                        st.session_state.pinned_video = (vid, st.session_state.playing_title)
                    st.rerun()
            with btn_fav:
                is_fav_now = vid in [f[0] for f in st.session_state.favorites]
                fav_btn_lbl = "⭐ Unfav" if is_fav_now else "☆ Fav"
                if st.button(fav_btn_lbl, key="fav_player_btn"):
                    toggle_favorite(vid, st.session_state.playing_title); st.rerun()

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
                    {like_ratio_bar_html(stats)}
                    <p style="font-size:{FS_META};color:{MUTED2};margin-top:8px">{snip.get('channelTitle','')}</p>
                    <p style="font-size:{FS_META};color:{MUTED};line-height:1.5">{snip.get('description','')[:280]}{"…" if len(snip.get('description',''))>280 else ""}</p>
                    """, unsafe_allow_html=True)
            st.markdown(f'<a href="https://youtu.be/{vid}" style="color:{ACCENT};font-size:{FS_META}" target="_blank">↗ Open on YouTube</a>', unsafe_allow_html=True)
            _render_share = True

    # ── Video Notes ──
    with st.expander("📝 Notes for this video"):
        existing_note = st.session_state.video_notes.get(vid, "")
        note = st.text_area("Your notes", value=existing_note, height=80, key=f"note_{vid}", label_visibility="collapsed", placeholder="Add personal notes about this video…")
        if note != existing_note:
            st.session_state.video_notes[vid] = note
        if existing_note:
            st.markdown(f'<div class="notes-box">{existing_note}</div>', unsafe_allow_html=True)

    # ── Share & Embed ──
    if _render_share:
        with st.expander("🔗 Share & Embed"):
            yt_url, wa_url, tg_url, tw_url, embed_code = share_links_html(vid, st.session_state.playing_title)

            # Short URL
            sc_short, sc_qr = st.columns([2, 1])
            with sc_short:
                st.markdown(f"<p style='font-size:{FS_META};font-weight:600;color:{TEXT}'>Shareable link</p>", unsafe_allow_html=True)
                st.markdown(f'<div class="share-link-box">{yt_url}</div>', unsafe_allow_html=True)
                if st.button("🔗 Get Short URL (TinyURL)", key="tinyurl_btn"):
                    with st.spinner("Shortening…"):
                        short = get_short_url(vid, yt_url)
                    st.session_state.short_url_cache[vid] = short
                    st.markdown(f'<div class="share-link-box">{short}</div>', unsafe_allow_html=True)
                    st.markdown(f'<button onclick="copyToClipboard(\'{short}\')" style="background:{ACCENT};color:#fff;border:none;border-radius:8px;padding:6px 14px;cursor:pointer;font-size:{FS_SMALL};margin-top:4px">📋 Copy short URL</button>', unsafe_allow_html=True)

                # Copy embed code
                safe_embed = embed_code.replace("'", "\\'")
                st.markdown(f'<button onclick="copyToClipboard(\'{safe_embed}\')" style="background:{CARD_BG};color:{TEXT};border:1px solid {BORDER2};border-radius:8px;padding:6px 14px;cursor:pointer;font-size:{FS_SMALL};margin-top:4px">📋 Copy embed code</button>', unsafe_allow_html=True)

            with sc_qr:
                st.markdown(f"<p style='font-size:{FS_META};font-weight:600;color:{TEXT}'>QR Code</p>", unsafe_allow_html=True)
                qr_target = st.session_state.short_url_cache.get(vid, yt_url)
                qr_png = make_qr_png(qr_target)
                st.image(qr_png, width=150)
                st.caption("Scans to: " + qr_target)
                st.download_button(
                    "Download QR PNG",
                    data=qr_png,
                    file_name=f"tubeplay-{vid}-qr.png",
                    mime="image/png",
                    use_container_width=True,
                )

            # Share buttons row
            sb1, sb2, sb3, sb4 = st.columns(4)
            li_url = "https://www.linkedin.com/sharing/share-offsite/?url=" + urllib.parse.quote(yt_url)
            with sb1:
                st.markdown(f'<a href="{wa_url}" target="_blank" style="display:block;background:#25d366;color:#fff;text-align:center;padding:8px 0;border-radius:8px;text-decoration:none;font-weight:600;font-size:{FS_META};">📱 WhatsApp</a>', unsafe_allow_html=True)
            with sb2:
                st.markdown(f'<a href="{tg_url}" target="_blank" style="display:block;background:#229ed9;color:#fff;text-align:center;padding:8px 0;border-radius:8px;text-decoration:none;font-weight:600;font-size:{FS_META};">✈️ Telegram</a>', unsafe_allow_html=True)
            with sb3:
                st.markdown(f'<a href="{tw_url}" target="_blank" style="display:block;background:#1DA1F2;color:#fff;text-align:center;padding:8px 0;border-radius:8px;text-decoration:none;font-weight:600;font-size:{FS_META};">🐦 Twitter/X</a>', unsafe_allow_html=True)
            with sb4:
                st.markdown(f'<a href="{li_url}" target="_blank" style="display:block;background:#0A66C2;color:#fff;text-align:center;padding:8px 0;border-radius:8px;text-decoration:none;font-weight:600;font-size:{FS_META};">💼 LinkedIn</a>', unsafe_allow_html=True)

            st.code(embed_code, language="html")

    st.divider()

# ─── Search ──────────────────────────────────────────────────────────────────
st.markdown("#### 🔍 Search YouTube")
if not api_key:
    st.warning("Add your free YouTube Data API v3 key in the sidebar to enable search.")
else:
    search_col, btn_col = st.columns([5, 1])
    with search_col:
        query = st.text_input("Search query", placeholder="lo-fi hip hop, coding tutorials…",
                              label_visibility="collapsed", key="search_query")
    with btn_col:
        do_search = st.button("Search", use_container_width=True)

    # Search filter row
    sf1, sf2, sf3 = st.columns(3)
    with sf1:
        s_order = st.selectbox("Sort by", ["relevance", "date", "viewCount", "rating", "title"],
                               index=["relevance","date","viewCount","rating","title"].index(st.session_state.search_order),
                               key="s_order", label_visibility="collapsed")
        if s_order != st.session_state.search_order:
            st.session_state.search_order = s_order
    with sf2:
        s_type = st.selectbox("Type", ["video", "channel", "playlist"],
                              index=["video","channel","playlist"].index(st.session_state.search_type),
                              key="s_type", label_visibility="collapsed")
        if s_type != st.session_state.search_type:
            st.session_state.search_type = s_type
    with sf3:
        s_safe = st.checkbox("Safe search", value=st.session_state.search_safe, key="s_safe")
        if s_safe != st.session_state.search_safe:
            st.session_state.search_safe = s_safe

    if do_search and query:
        with st.spinner("Searching…"):
            results, err = search_youtube(query, api_key,
                                          order=st.session_state.search_order,
                                          video_type=st.session_state.search_type,
                                          safe=st.session_state.search_safe)
        if err:
            st.error(err)
        elif results:
            st.session_state.search_results = results
        else:
            st.info("No results found.")

    if st.session_state.search_results:
        st.markdown(f"<p style='color:{MUTED};font-size:{FS_SMALL}'>Showing {len(st.session_state.search_results)} results — click ▶ to play or + to queue</p>", unsafe_allow_html=True)
        cols = st.columns(4)
        for i, item in enumerate(st.session_state.search_results):
            vid_id  = item["id"]["videoId"]
            snip    = item["snippet"]
            thumb   = snip["thumbnails"].get("medium", snip["thumbnails"].get("default", {})).get("url", "")
            title   = snip.get("title", "Untitled")
            channel = snip.get("channelTitle", "")

            with cols[i % 4]:
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
                pb1, pb2, pb3 = st.columns([3, 1, 1])
                with pb1:
                    if st.button(f"▶ {short}", key=f"play_{vid_id}", use_container_width=True):
                        play_video(vid_id, title); st.rerun()
                with pb2:
                    if st.button("+", key=f"queue_{vid_id}", use_container_width=True):
                        if vid_id not in [q[0] for q in st.session_state.queue]:
                            st.session_state.queue.append((vid_id, title)); st.rerun()
                with pb3:
                    is_fav = vid_id in [f[0] for f in st.session_state.favorites]
                    fav_lbl = "⭐" if is_fav else "☆"
                    if st.button(fav_lbl, key=f"fav_{vid_id}", use_container_width=True, help="Favorite"):
                        toggle_favorite(vid_id, title); st.rerun()

# ─── Info expander ───────────────────────────────────────────────────────────
with st.expander("ℹ️ How to get a free YouTube Data API v3 key"):
    st.markdown("""
1. Go to [console.developers.google.com](https://console.developers.google.com)
2. Create a project → Enable **YouTube Data API v3**
3. Credentials → Create Credentials → API Key
4. Paste in the sidebar

**Free quota:** 10,000 units/day (~100 searches). Embedding is always free.
    """)
