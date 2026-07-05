# ▶️ TubePlay — In-Site YouTube Player

A sleek Streamlit app to play YouTube videos embedded in your own site, with search powered by the free YouTube Data API v3.

## Features
- 🎬 **Play any YouTube video** by URL or ID — no API key needed
- 🔍 **Search YouTube** from inside the app (needs free API key)
- 📊 **Video stats** — views, likes, description, channel
- 🕒 **Watch history** — recent videos in sidebar
- 🎨 **Dark UI** — minimal, distraction-free player

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run the app
streamlit run app.py
```

The app opens at `http://localhost:8501`

## Getting a Free API Key (optional, for search)

1. Visit https://console.developers.google.com
2. Create a project → Enable **YouTube Data API v3**
3. Credentials → Create Credentials → API Key
4. Paste it in the sidebar

**Free quota:** 10,000 units/day (~100 searches). Embedding/playing is always free.

## Embed Player vs API

| Feature | Needs API Key? |
|---|---|
| Play by URL/ID | ❌ No |
| Video stats/info | ✅ Yes |
| Search YouTube | ✅ Yes |

## Deploy to Streamlit Cloud (free)

1. Push this folder to GitHub
2. Go to https://share.streamlit.io
3. Connect your repo and deploy — free hosting!
