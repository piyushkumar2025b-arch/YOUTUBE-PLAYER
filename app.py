import streamlit as st
import requests
import re
import urllib.parse
import json
import io
import csv
import base64
import os
import subprocess
import sys
from pathlib import Path
import qrcode
from PIL import Image

# ── Feature modules (small, self-contained) ───────────────────────────────────
from channel_info          import render_channel_panel
from video_comments        import render_comments_panel
from watch_stats           import record_watch_event, render_stats_dashboard
from scheduler             import render_scheduler_panel, check_and_fire_scheduled
from speedread_transcript  import render_speedread_panel
from video_clipper         import render_clipper_panel
from video_summarizer      import render_summarizer_panel
from study_focus           import render_focus_panel

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
    "watch_later": [],      # list of (vid_id, title)
    "sleep_timer_mins": 0,  # 0 = off
    "sleep_timer_start": None,
    "watch_count": 0,       # total videos watched this session
    "search_order": "relevance",
    "search_type": "video",
    "search_safe": False,
    "download_dir": "",
    "last_download_path": "",
    "saved_playlists": {},  # name -> list of (vid_id, title)
    "related_results": [],
    "trending_results": [],
    "transcript_cache": {},  # vid_id -> transcript text
    "timestamped_notes": {}, # vid_id -> list of {"time": "1:23", "note": "..."}
    "video_clips": {},       # video_id -> list of {"title": str, "start": int, "end": int}
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

def get_playlist_id(url_or_id: str) -> str | None:
    value = (url_or_id or "").strip()
    if not value:
        return None
    if re.match(r"^[A-Za-z0-9_-]{16,}$", value) and "youtube" not in value:
        return value
    parsed = urllib.parse.urlparse(value)
    query = urllib.parse.parse_qs(parsed.query)
    return (query.get("list") or [None])[0]

def import_youtube_playlist(playlist_id: str, api_key: str, limit: int = 50):
    url = "https://www.googleapis.com/youtube/v3/playlistItems"
    videos, page_token = [], None
    try:
        while len(videos) < limit:
            params = {
                "part": "snippet",
                "playlistId": playlist_id,
                "maxResults": min(50, limit - len(videos)),
                "key": api_key,
            }
            if page_token:
                params["pageToken"] = page_token
            r = requests.get(url, params=params, timeout=10)
            if r.status_code != 200:
                return None, f"Playlist API error {r.status_code}"
            data = r.json()
            for item in data.get("items", []):
                snip = item.get("snippet", {})
                resource = snip.get("resourceId", {})
                vid = resource.get("videoId")
                title = snip.get("title", vid or "Untitled")
                if vid:
                    videos.append((vid, title))
            page_token = data.get("nextPageToken")
            if not page_token:
                break
        return videos, None
    except Exception as exc:
        return None, f"Playlist import failed: {exc}"

def get_trending_videos(api_key: str, region: str = "US", category: str = "0", max_results: int = 12):
    params = {
        "part": "snippet,statistics",
        "chart": "mostPopular",
        "regionCode": region,
        "maxResults": max_results,
        "key": api_key,
    }
    if category != "0":
        params["videoCategoryId"] = category
    try:
        r = requests.get("https://www.googleapis.com/youtube/v3/videos", params=params, timeout=10)
        if r.status_code != 200:
            return None, f"Trending API error {r.status_code}"
        return r.json().get("items", []), None
    except Exception as exc:
        return None, f"Trending request failed: {exc}"

def get_related_videos(video_id: str, api_key: str, max_results: int = 12):
    info = get_video_info(video_id, api_key)
    if not info:
        return None, "Could not load the current video's details."
    snip = info.get("snippet", {})
    topic = " ".join([snip.get("title", ""), snip.get("channelTitle", "")]).strip()
    return search_youtube(topic, api_key, max_results=max_results, order="relevance", video_type="video")

def get_video_transcript(video_id: str) -> tuple[str | None, str | None]:
    if video_id in st.session_state.transcript_cache:
        return st.session_state.transcript_cache[video_id], None
    url = f"https://video.google.com/timedtext?lang=en&v={video_id}"
    try:
        r = requests.get(url, timeout=8)
        if r.status_code != 200 or not r.text.strip():
            return None, "No English transcript was found for this video."
        parts = re.findall(r'<text[^>]*start="([^"]+)"[^>]*>(.*?)</text>', r.text, flags=re.S)
        lines = []
        for start, raw in parts:
            seconds = int(float(start))
            stamp = f"{seconds // 60}:{seconds % 60:02d}"
            text = re.sub(r"<[^>]+>", "", raw)
            text = urllib.parse.unquote(text).replace("&amp;", "&").replace("&#39;", "'").replace("&quot;", '"')
            if text.strip():
                lines.append(f"[{stamp}] {text.strip()}")
        transcript = "\n".join(lines)
        if not transcript:
            return None, "Transcript data was empty."
        st.session_state.transcript_cache[video_id] = transcript
        return transcript, None
    except Exception as exc:
        return None, f"Transcript request failed: {exc}"

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
    player_params = {
        "autoplay": int(autoplay), "rel": 0,
        "modestbranding": 1, "enablejsapi": 1,
        "start": start,
        "loop": int(loop),
    }
    if loop:
        player_params["playlist"] = video_id
    params = urllib.parse.urlencode(player_params)
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

def default_download_dir() -> str:
    desktop = Path.home() / "Desktop"
    base = desktop if desktop.exists() else Path.home() / "Downloads"
    return str(base / "TubePlay Downloads")

def download_video_locally(video_id: str, title: str, folder: str, quality: str) -> tuple[bool, str]:
    target_dir = Path(folder).expanduser()
    try:
        target_dir.mkdir(parents=True, exist_ok=True)
    except Exception as exc:
        return False, f"Could not create folder: {exc}"

    url = f"https://www.youtube.com/watch?v={video_id}"
    output_template = str(target_dir / "%(title).180s [%(id)s].%(ext)s")
    if quality == "Audio only":
        format_selector = "bestaudio/best"
        extra_args = ["--extract-audio", "--audio-format", "mp3"]
    elif quality == "Small MP4":
        format_selector = "bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/best[height<=480][ext=mp4]/best[height<=480]"
        extra_args = []
    else:
        format_selector = "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720][ext=mp4]/best[height<=720]"
        extra_args = []

    cmd = [
        sys.executable, "-m", "yt_dlp",
        "--no-playlist",
        "--restrict-filenames",
        "-f", format_selector,
        "-o", output_template,
        "--print", "after_move:filepath",
        *extra_args,
        url,
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
    except FileNotFoundError:
        return False, "Python could not start the downloader."
    except subprocess.TimeoutExpired:
        return False, "Download took too long and was stopped."

    if result.returncode != 0:
        error = (result.stderr or result.stdout or "Unknown downloader error").strip()
        if "No module named yt_dlp" in error:
            return False, "yt-dlp is not installed. Run: pip install -r requirements.txt"
        return False, error[-700:]

    saved_lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    saved_path = saved_lines[-1] if saved_lines else str(target_dir)
    st.session_state.last_download_path = saved_path
    return True, saved_path

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

def export_library_json() -> bytes:
    data = {
        "queue": st.session_state.queue,
        "favorites": st.session_state.favorites,
        "watch_later": st.session_state.watch_later,
        "history": st.session_state.history,
        "notes": st.session_state.video_notes,
        "timestamped_notes": st.session_state.timestamped_notes,
        "saved_playlists": st.session_state.saved_playlists,
        "video_clips": st.session_state.video_clips,
    }
    return json.dumps(data, indent=2, ensure_ascii=False).encode("utf-8")

def import_library_json(raw: bytes) -> tuple[bool, str]:
    try:
        data = json.loads(raw.decode("utf-8"))
    except Exception as exc:
        return False, f"Could not read JSON: {exc}"

    def clean_pairs(value):
        cleaned = []
        for item in value or []:
            if isinstance(item, (list, tuple)) and len(item) >= 2:
                vid, title = str(item[0]), str(item[1])
                if re.match(r"^[A-Za-z0-9_-]{11}$", vid):
                    cleaned.append((vid, title))
        return cleaned

    for key in ["queue", "favorites", "watch_later", "history"]:
        if key in data:
            existing = [x[0] for x in st.session_state[key]]
            st.session_state[key].extend([x for x in clean_pairs(data[key]) if x[0] not in existing])
    if isinstance(data.get("notes"), dict):
        st.session_state.video_notes.update({str(k): str(v) for k, v in data["notes"].items()})
    if isinstance(data.get("timestamped_notes"), dict):
        st.session_state.timestamped_notes.update(data["timestamped_notes"])
    if isinstance(data.get("saved_playlists"), dict):
        st.session_state.saved_playlists.update({
            str(name): clean_pairs(items)
            for name, items in data["saved_playlists"].items()
        })
    if isinstance(data.get("video_clips"), dict):
        st.session_state.video_clips.update(data["video_clips"])
    return True, "Library imported"

def import_queue_text(raw: bytes):
    text = raw.decode("utf-8", errors="ignore")
    return parse_bulk_urls(text)

def play_video(vid_id: str, title: str, channel: str = ""):
    st.session_state.playing_id = vid_id
    st.session_state.playing_title = title
    st.session_state.scroll_to_player = True
    st.session_state.watch_count += 1
    # Record watch event for analytics
    record_watch_event(vid_id, title, channel_name=channel)
    if vid_id not in [h[0] for h in st.session_state.history]:
        st.session_state.history.insert(0, (vid_id, title))
        st.session_state.history = st.session_state.history[:20]

def toggle_favorite(vid_id: str, title: str):
    ids = [f[0] for f in st.session_state.favorites]
    if vid_id in ids:
        st.session_state.favorites = [f for f in st.session_state.favorites if f[0] != vid_id]
    else:
        st.session_state.favorites.insert(0, (vid_id, title))

def toggle_watch_later(vid_id: str, title: str):
    ids = [w[0] for w in st.session_state.watch_later]
    if vid_id in ids:
        st.session_state.watch_later = [w for w in st.session_state.watch_later if w[0] != vid_id]
    else:
        st.session_state.watch_later.insert(0, (vid_id, title))

def add_unique_to_queue(items):
    existing_ids = [q[0] for q in st.session_state.queue]
    new_items = [item for item in items if item[0] not in existing_ids]
    st.session_state.queue.extend(new_items)
    return len(new_items)

def render_video_grid(items, key_prefix: str):
    if not items:
        return
    cols = st.columns(4)
    for i, item in enumerate(items):
        if "snippet" in item:
            vid_id = item.get("id", {}).get("videoId") if isinstance(item.get("id"), dict) else item.get("id")
            snip = item.get("snippet", {})
            thumb = snip.get("thumbnails", {}).get("medium", snip.get("thumbnails", {}).get("default", {})).get("url", "")
            title = snip.get("title", "Untitled")
            channel = snip.get("channelTitle", "")
        else:
            vid_id, title = item
            thumb = f"https://img.youtube.com/vi/{vid_id}/mqdefault.jpg"
            channel = ""
        if not vid_id:
            continue
        with cols[i % 4]:
            st.markdown(f"""
            <div class="video-card">
              <img src="{thumb}" alt="{title}">
              <div class="video-card-body">
                <p class="video-card-title">{title}</p>
                <span class="video-card-meta">{channel}</span>
              </div>
            </div>
            """, unsafe_allow_html=True)
            short = title[:22] + "..." if len(title) > 22 else title
            c1, c2, c3 = st.columns([3, 1, 1])
            with c1:
                if st.button(f"Play {short}", key=f"{key_prefix}_play_{i}_{vid_id}", use_container_width=True):
                    play_video(vid_id, title); st.rerun()
            with c2:
                if st.button("+", key=f"{key_prefix}_queue_{i}_{vid_id}", use_container_width=True):
                    add_unique_to_queue([(vid_id, title)]); st.rerun()
            with c3:
                if st.button("*", key=f"{key_prefix}_fav_{i}_{vid_id}", use_container_width=True, help="Favorite"):
                    toggle_favorite(vid_id, title); st.rerun()

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

        loop = st.checkbox("🔁 Loop", value=st.session_state.loop_mode, key="loop_cb")
        if loop != st.session_state.loop_mode:
            st.session_state.loop_mode = loop
        shuffle = st.checkbox("🔀 Shuffle", value=st.session_state.shuffle_mode, key="shuf_cb")
        if shuffle != st.session_state.shuffle_mode:
            st.session_state.shuffle_mode = shuffle
        auto_n = st.checkbox("⏭ Auto-next", value=st.session_state.autoplay_next, key="auto_cb")
        if auto_n != st.session_state.autoplay_next:
            st.session_state.autoplay_next = auto_n

    st.divider()

    # ── API Key ──
    st.markdown("#### 🔑 API Key")
    api_key = st.text_input("YouTube Data API v3 key", type="password", placeholder="AIza…", key="api_key_input")
    st.divider()

    quick_tab, playlists_tab, library_tab, focus_tab = st.tabs(["Quick", "Playlists", "Library", "Focus"])

    with focus_tab:
        render_focus_panel(api_key)

    with playlists_tab:
        st.markdown("#### Import YouTube Playlist")
        playlist_url = st.text_input("Playlist URL or ID", key="playlist_url", placeholder="https://youtube.com/playlist?list=...")
        playlist_limit = st.slider("Max videos", 5, 100, 50, 5, key="playlist_limit")
        if st.button("Import playlist to queue", use_container_width=True):
            if not api_key:
                st.error("Add your YouTube API key first.")
            else:
                playlist_id = get_playlist_id(playlist_url)
                if not playlist_id:
                    st.error("Could not find a playlist ID.")
                else:
                    with st.spinner("Importing playlist..."):
                        videos, err = import_youtube_playlist(playlist_id, api_key, playlist_limit)
                    if err:
                        st.error(err)
                    else:
                        count = add_unique_to_queue(videos)
                        st.success(f"Added {count} video(s) to queue.")
                        st.rerun()

        st.markdown("#### Save / Load Queue")
        save_name = st.text_input("Playlist name", key="save_playlist_name", placeholder="My study mix")
        if st.button("Save current queue", use_container_width=True):
            if save_name and st.session_state.queue:
                st.session_state.saved_playlists[save_name] = list(st.session_state.queue)
                st.success("Playlist saved.")
            else:
                st.warning("Add a name and at least one queued video.")
        if st.session_state.saved_playlists:
            selected_playlist = st.selectbox("Saved playlists", list(st.session_state.saved_playlists.keys()), key="saved_playlist_select")
            if st.button("Load playlist", use_container_width=True):
                add_unique_to_queue(st.session_state.saved_playlists[selected_playlist])
                st.rerun()
            if st.button("Replace queue", use_container_width=True):
                st.session_state.queue = list(st.session_state.saved_playlists[selected_playlist])
                st.session_state.queue_index = 0
                st.rerun()

    with library_tab:
        st.markdown("#### Search Saved Videos")
        lib_query = st.text_input("Search saved videos", key="library_search", placeholder="Queue, favorites, later, history")
        all_saved = []
        for source_name in ["queue", "favorites", "watch_later", "history"]:
            for vid_id, title in st.session_state[source_name]:
                all_saved.append((vid_id, title, source_name.replace("_", " ")))
        if lib_query:
            matches = [x for x in all_saved if lib_query.lower() in x[1].lower() or lib_query.lower() in x[0].lower()]
            for vid_id, title, source in matches[:12]:
                label = f"{title[:28]}{'...' if len(title) > 28 else ''} ({source})"
                if st.button(label, key=f"lib_search_{source}_{vid_id}", use_container_width=True):
                    play_video(vid_id, title); st.rerun()
            if not matches:
                st.caption("No saved videos matched.")

        st.download_button("Export library.json", data=export_library_json(),
                           file_name="tubeplay_library.json", mime="application/json",
                           use_container_width=True, key="export_library_json_tab")
        library_upload_tab = st.file_uploader("Import library.json", type=["json"], key="library_upload_tab")
        if library_upload_tab and st.button("Import library file", use_container_width=True):
            ok, msg = import_library_json(library_upload_tab.getvalue())
            st.success(msg) if ok else st.error(msg)
            if ok:
                st.rerun()

    # ── Play by URL / ID ──
    with quick_tab:
        st.markdown("#### Play by URL / ID")
        direct_url = st.text_input("YouTube URL or Video ID", placeholder="https://youtu.be/... or dQw4w9WgXcQ", key="direct_url")
        col_a, col_b = st.columns([1, 1])
        with col_a:
            if st.button("Play", use_container_width=True):
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
                    add_unique_to_queue([(vid, title)])
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

    queue_upload = st.file_uploader("Import queue file", type=["txt", "csv"], key="queue_upload", label_visibility="collapsed")
    if queue_upload and st.button("Import Queue File", use_container_width=True):
        added = import_queue_text(queue_upload.getvalue())
        existing_ids = [q[0] for q in st.session_state.queue]
        new = [x for x in added if x[0] not in existing_ids]
        st.session_state.queue.extend(new)
        st.success(f"Imported {len(new)} video(s)")
        st.rerun()

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
            col_up, col_down, col_later, col_rm = st.columns(4)
            with col_up:
                if st.button("↑", key=f"up_q_{i}_{qid}", use_container_width=True, disabled=i == 0):
                    st.session_state.queue[i - 1], st.session_state.queue[i] = st.session_state.queue[i], st.session_state.queue[i - 1]
                    st.session_state.queue_index = max(st.session_state.queue_index - 1, 0)
                    st.rerun()
            with col_down:
                if st.button("↓", key=f"down_q_{i}_{qid}", use_container_width=True, disabled=i == len(st.session_state.queue) - 1):
                    st.session_state.queue[i + 1], st.session_state.queue[i] = st.session_state.queue[i], st.session_state.queue[i + 1]
                    st.session_state.queue_index = min(st.session_state.queue_index + 1, len(st.session_state.queue) - 1)
                    st.rerun()
            with col_later:
                if st.button("⏳", key=f"later_q_{i}_{qid}", use_container_width=True, help="Save for later"):
                    toggle_watch_later(qid, qtitle); st.rerun()
            with col_rm:
                if st.button("×", key=f"rm_q_{i}_{qid}", use_container_width=True, help="Remove"):
                    st.session_state.queue.pop(i)
                    st.session_state.queue_index = min(st.session_state.queue_index, max(len(st.session_state.queue) - 1, 0))
                    st.rerun()

        qc1, qc2, qc3, qc4 = st.columns(4)
        with qc1:
            if st.button("⏮ Prev", use_container_width=True):
                idx = max(st.session_state.queue_index - 1, 0)
                qid, qtitle = st.session_state.queue[idx]
                play_video(qid, qtitle); st.session_state.queue_index = idx; st.rerun()
        with qc2:
            if st.button("⏭ Next", use_container_width=True):
                if st.session_state.shuffle_mode:
                    import random
                    idx = random.randint(0, len(st.session_state.queue)-1)
                else:
                    idx = min(st.session_state.queue_index + 1, len(st.session_state.queue)-1)
                qid, qtitle = st.session_state.queue[idx]
                play_video(qid, qtitle); st.session_state.queue_index = idx; st.rerun()
        with qc3:
            if st.button("🔀 Shuf", use_container_width=True):
                import random
                random.shuffle(st.session_state.queue)
                st.rerun()
        with qc4:
            if st.button("🗑 Clear", use_container_width=True):
                st.session_state.queue = []; st.session_state.queue_index = 0; st.rerun()

        st.divider()

    # ── Watch Later ──
    if st.session_state.watch_later:
        st.markdown("#### ⏳ Watch Later")
        for later_id, later_title in st.session_state.watch_later[:8]:
            wl_label = later_title[:28] + "…" if len(later_title) > 28 else later_title
            if st.button(f"▶ {wl_label}", key=f"later_play_{later_id}", use_container_width=True):
                play_video(later_id, later_title); st.rerun()
            if st.button(f"× Remove '{later_title[:18]}…'", key=f"later_rm_{later_id}", use_container_width=True):
                st.session_state.watch_later = [w for w in st.session_state.watch_later if w[0] != later_id]
                st.rerun()
        st.divider()

    # ── Pinned Video ──
    if st.session_state.pinned_video:
        pvid, ptitle = st.session_state.pinned_video
        short_p = ptitle[:24] + "…" if len(ptitle) > 24 else ptitle
        st.markdown(f"#### 📌 Pinned")
        if st.button(f"▶ {short_p}", key="play_pinned", use_container_width=True):
            play_video(pvid, ptitle); st.rerun()
        if st.button("✕ Unpin", key="unpin", use_container_width=True):
            st.session_state.pinned_video = None; st.rerun()
        st.divider()

    # ── Favorites ──
    if st.session_state.favorites:
        st.markdown("#### ⭐ Favorites")
        for fav_id, fav_title in st.session_state.favorites[:8]:
            flbl = ("▶ " if fav_id == st.session_state.playing_id else "") + (fav_title[:26] + "…" if len(fav_title) > 26 else fav_title)
            if st.button(flbl, key=f"fav_play_{fav_id}", use_container_width=True):
                play_video(fav_id, fav_title); st.rerun()
            if st.button(f"✕ Remove", key=f"fav_rm_{fav_id}", use_container_width=True):
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
        if st.button("▶ Resume last", use_container_width=True):
            vid_id, title = st.session_state.history[0]
            play_video(vid_id, title); st.rerun()
        if st.button("🗑 Clear history", use_container_width=True):
            st.session_state.history = []; st.rerun()
        st.download_button("⬇ Export history.csv", data=export_history_csv(),
                           file_name="tubeplay_history.csv", mime="text/csv",
                           use_container_width=True)
        st.divider()

    # ── Library backup ──
    with st.expander("💾 Library Backup"):
        st.download_button("Export library.json", data=export_library_json(),
                           file_name="tubeplay_library.json", mime="application/json",
                           use_container_width=True, key="export_library_json_backup")
        library_upload = st.file_uploader("Import library.json", type=["json"], key="library_upload")
        if library_upload and st.button("Import Library", use_container_width=True):
            ok, msg = import_library_json(library_upload.getvalue())
            st.success(msg) if ok else st.error(msg)
            if ok:
                st.rerun()

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
# Fire any due scheduled events before rendering the player
check_and_fire_scheduled()

st.markdown("## ▶️ TubePlay")

# ── Session Stats Bar ──
if st.session_state.watch_count > 0 or st.session_state.queue or st.session_state.favorites or st.session_state.watch_later:
    fav_count = len(st.session_state.favorites)
    q_count = len(st.session_state.queue)
    h_count = len(st.session_state.history)
    later_count = len(st.session_state.watch_later)
    playlist_count = len(st.session_state.saved_playlists)
    note_count = len(st.session_state.video_notes) + sum(len(v) for v in st.session_state.timestamped_notes.values())
    st.markdown(f"""
    <div class="stats-bar">
      <div class="stat-item">🎬 Watched: <span>{st.session_state.watch_count}</span></div>
      <div class="stat-item">🎵 Queue: <span>{q_count}</span></div>
      <div class="stat-item">⭐ Favorites: <span>{fav_count}</span></div>
      <div class="stat-item">⏳ Later: <span>{later_count}</span></div>
      <div class="stat-item">🕒 History: <span>{h_count}</span></div>
      <div class="stat-item">📚 Playlists: <span>{playlist_count}</span></div>
      <div class="stat-item">📝 Notes: <span>{note_count}</span></div>
    </div>
    """, unsafe_allow_html=True)

# Mini player overlay disabled so playback stays in the main allotted player area.

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
        ("🎵", "Queue", "Build and reorder a playlist from any URLs"),
        ("📚", "Playlists", "Import YouTube playlists or save your own"),
        ("🔥", "Discover", "Browse trending and related videos"),
        ("📝", "Notes", "Keep normal and timestamped notes"),
        ("📄", "Transcripts", "Load, search, and export captions"),
        ("⭐", "Library", "Search favorites, later, queue, and history"),
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
            btn_fs, btn_pip, btn_pin, btn_fav, btn_later, _ = st.columns([1, 1, 1, 1, 1, 1])
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
            with btn_later:
                is_later_now = vid in [w[0] for w in st.session_state.watch_later]
                later_btn_lbl = "✓ Later" if is_later_now else "⏳ Later"
                if st.button(later_btn_lbl, key="later_player_btn"):
                    toggle_watch_later(vid, st.session_state.playing_title); st.rerun()

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
        st.markdown("##### Timestamped notes")
        tc1, tc2 = st.columns([1, 3])
        with tc1:
            note_time = st.text_input("Time", placeholder="1:23", key=f"ts_time_{vid}", label_visibility="collapsed")
        with tc2:
            note_text = st.text_input("Note", placeholder="Important moment...", key=f"ts_note_{vid}", label_visibility="collapsed")
        if st.button("Add timestamped note", key=f"add_ts_note_{vid}"):
            if note_time and note_text:
                st.session_state.timestamped_notes.setdefault(vid, []).append({"time": note_time, "note": note_text})
                st.rerun()
        for idx, item in enumerate(st.session_state.timestamped_notes.get(vid, [])):
            n1, n2 = st.columns([5, 1])
            with n1:
                st.markdown(f"`{item.get('time', '')}` {item.get('note', '')}")
            with n2:
                if st.button("×", key=f"rm_ts_{vid}_{idx}"):
                    st.session_state.timestamped_notes[vid].pop(idx)
                    st.rerun()

    with st.expander("📄 Transcript"):
        if st.button("Load transcript", key=f"load_transcript_{vid}"):
            with st.spinner("Checking captions..."):
                transcript, err = get_video_transcript(vid)
            if err:
                st.warning(err)
            else:
                st.session_state.transcript_cache[vid] = transcript
        transcript = st.session_state.transcript_cache.get(vid)
        if transcript:
            transcript_query = st.text_input("Search transcript", key=f"transcript_search_{vid}", placeholder="Find a phrase")
            shown_transcript = transcript
            if transcript_query:
                shown_transcript = "\n".join([line for line in transcript.splitlines() if transcript_query.lower() in line.lower()])
            st.text_area("Transcript text", value=shown_transcript, height=220, key=f"transcript_text_{vid}", label_visibility="collapsed")
            st.download_button("Export transcript.txt", data=transcript.encode("utf-8"),
                               file_name=f"tubeplay-{vid}-transcript.txt", mime="text/plain",
                               use_container_width=True)

    # ── Local Download ──
    with st.expander("⬇ Download locally"):
        st.caption("Saves videos you own or have permission to download. On Streamlit Cloud this saves on the server; run locally to save on this laptop.")
        if not st.session_state.download_dir:
            st.session_state.download_dir = default_download_dir()
        dl_dir = st.text_input("Download location", value=st.session_state.download_dir, key="download_dir_input")
        st.session_state.download_dir = dl_dir
        dl_quality = st.selectbox("Format", ["MP4 up to 720p", "Small MP4", "Audio only"], key="download_quality")
        if st.button("Download this video", key="download_video_btn", use_container_width=True):
            with st.spinner("Downloading to your selected folder..."):
                ok, message = download_video_locally(vid, st.session_state.playing_title, dl_dir, dl_quality)
            if ok:
                st.success("Saved to: " + message)
            else:
                st.error(message)
        if st.session_state.last_download_path:
            st.info("Last saved file: " + st.session_state.last_download_path)

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

    # ── Clipper & Loops ──
    with st.expander("✂️ Video Clipper & Chapters"):
        render_clipper_panel(vid, st.session_state.playing_title)

    # ── Smart Transcript Summarizer ──
    with st.expander("⚡ Smart Transcript Summarizer"):
        render_summarizer_panel(vid, st.session_state.transcript_cache.get(vid), api_key)

    # ── Comments ──
    with st.expander("💬 Comments"):
        render_comments_panel(vid, api_key)

    # ── Speed-Read Transcript ──
    with st.expander("⚡ Speed-Read Transcript"):
        render_speedread_panel(vid, st.session_state.transcript_cache.get(vid))

# ─── Discover ─────────────────────────────────────────────────────────────────
with st.expander("🔥 Discover"):
    if not api_key:
        st.caption("Add your YouTube API key in the sidebar to use trending and related videos.")
    else:
        d1, d2, d3 = st.columns([1, 1, 1])
        with d1:
            region = st.selectbox("Region", ["US", "IN", "GB", "CA", "AU", "DE", "FR", "JP", "BR"], key="trend_region")
        with d2:
            category = st.selectbox(
                "Category",
                [("0", "All"), ("10", "Music"), ("20", "Gaming"), ("24", "Entertainment"), ("25", "News"), ("26", "How-to"), ("28", "Tech")],
                format_func=lambda item: item[1],
                key="trend_category",
            )
        with d3:
            st.write("")
            load_trending = st.button("Load trending", use_container_width=True)
        if load_trending:
            with st.spinner("Loading trending videos..."):
                results, err = get_trending_videos(api_key, region=region, category=category[0])
            if err:
                st.error(err)
            else:
                st.session_state.trending_results = results
        if st.session_state.trending_results:
            st.markdown("##### Trending")
            render_video_grid(st.session_state.trending_results, "trending")

        if st.session_state.playing_id:
            if st.button("Find related to current video", use_container_width=True):
                with st.spinner("Finding related videos..."):
                    results, err = get_related_videos(st.session_state.playing_id, api_key)
                if err:
                    st.error(err)
                else:
                    st.session_state.related_results = [
                        item for item in results
                        if item.get("id", {}).get("videoId") != st.session_state.playing_id
                    ]
            if st.session_state.related_results:
                st.markdown("##### Related")
                render_video_grid(st.session_state.related_results, "related")

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
                if st.button("⏳ Watch later", key=f"later_{vid_id}", use_container_width=True):
                    toggle_watch_later(vid_id, title); st.rerun()
# ─── Info expander ───────────────────────────────────────────────────────────
with st.expander("ℹ️ How to get a free YouTube Data API v3 key"):
    st.markdown("""
1. Go to [console.developers.google.com](https://console.developers.google.com)
2. Create a project → Enable **YouTube Data API v3**
3. Credentials → Create Credentials → API Key
4. Paste in the sidebar

**Free quota:** 10,000 units/day (~100 searches). Embedding is always free.
    """)
