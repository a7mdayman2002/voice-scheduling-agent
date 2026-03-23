# VoiceSchedule — AI Voice Scheduling Agent (FastAPI Backend)


## Loom Video
https://www.loom.com/share/e24fa51d827140dfad03774f7a38e2a8

A real-time voice assistant that schedules calendar events through natural conversation.
Powered by **Claude AI** (via a FastAPI backend), **Web Speech API** for voice I/O, and
calendar deep-links for Google Calendar, Outlook, and `.ics` download.

---

## 🏗️ Architecture

```
Browser (public/index.html)
        │
        │  POST /chat  { messages: [...] }
        ▼
FastAPI Server (backend/main.py)          ← ANTHROPIC_API_KEY lives here
        │
        │  anthropic.Anthropic().messages.create(...)
        ▼
Anthropic API  (claude-sonnet-4-20250514)
        │
        │  { reply, event_data }
        ▼
Browser renders event card + calendar links
```

The API key **never touches the browser** — the FastAPI server is the only
component that holds it.

---

## 📁 Project Structure

```
voice-scheduling-agent/
├── backend/
│   ├── main.py              ← FastAPI app (all AI logic here)
│   └── requirements.txt     ← Python dependencies
├── public/
│   └── index.html           ← Frontend (talks to /chat, /health)
├── .env.example             ← Copy to .env and add your key
├── .gitignore
├── Procfile                 ← For Railway / Render / Heroku
└── README.md
```

---

## 🚀 Running Locally

### 1. Clone & install

```bash
git clone https://github.com/yourusername/voice-scheduling-agent
cd voice-scheduling-agent

# Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r backend/requirements.txt
```

### 2. Set your API key

```bash
cp .env.example .env
# Edit .env and add your Anthropic API key:
#   ANTHROPIC_API_KEY=sk-ant-...
```

### 3. Start the server

```bash
uvicorn backend.main:app --reload --port 8000
```

The server starts at `http://localhost:8000`.

Open your browser to **http://localhost:8000** — the FastAPI server also serves
the `public/` frontend automatically via `StaticFiles`.

> **Note:** Web Speech API requires HTTPS or `localhost`. The local dev URL
> `http://localhost:8000` satisfies this requirement.

---

## 🌐 Deployment

### Option A — Railway (Recommended, free tier available)

```bash
# Install Railway CLI
npm install -g @railway/cli

railway login
railway init
railway up
```

Set the environment variable in the Railway dashboard:
```
ANTHROPIC_API_KEY=sk-ant-...
```

Railway auto-detects the `Procfile` and starts the server.

### Option B — Render

1. Push your repo to GitHub
2. Create a new **Web Service** on [render.com](https://render.com)
3. Set:
   - **Build command:** `pip install -r backend/requirements.txt`
   - **Start command:** `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`
4. Add environment variable: `ANTHROPIC_API_KEY=sk-ant-...`

### Option C — Heroku

```bash
heroku create your-app-name
heroku config:set ANTHROPIC_API_KEY=sk-ant-...
git push heroku main
```

### Option D — Docker

```bash
docker build -t voiceschedule .
docker run -p 8000:8000 -e ANTHROPIC_API_KEY=sk-ant-... voiceschedule
```

---

## 🔌 API Reference

### `GET /health`

Returns server status and confirms the API key is configured.

```json
{
  "status": "ok",
  "model": "claude-sonnet-4-20250514",
  "api_key_configured": true,
  "timestamp": "2026-03-19T10:00:00"
}
```

### `POST /chat`

Send the full conversation history; receive the assistant's reply.

**Request:**
```json
{
  "messages": [
    { "role": "user", "content": "Hi, I'd like to schedule a meeting" }
  ],
  "max_tokens": 500
}
```

**Response:**
```json
{
  "reply": "Hello! I'd love to help you schedule a meeting. What's your name?",
  "event_data": null
}
```

Once the AI has collected name + date + time:

```json
{
  "reply": "Perfect! I've prepared your event. Click Confirm Booking to add it to your calendar.",
  "event_data": {
    "name": "Sarah",
    "title": "Team Standup",
    "date": "2026-03-20",
    "time": "09:00",
    "duration": 30,
    "description": "Daily team standup"
  }
}
```

---

## 📅 Calendar Integration

Three export methods are supported (all client-side, no OAuth required):

| Method | How it works |
|--------|-------------|
| **Google Calendar** | Deep-link URL with pre-filled `text`, `dates`, `details` params — user clicks Save |
| **Outlook** | Deep-link to `outlook.live.com/calendar/compose` with pre-filled params |
| **Download .ics** | Client-side iCalendar file generation — opens in Apple Calendar, Thunderbird, etc. |

The iCalendar file follows RFC 5545 and includes `DTSTART`, `DTEND`, `SUMMARY`, `DESCRIPTION`, and a unique `UID`.

---

## 🎤 Voice Stack

| Component | Technology |
|-----------|-----------|
| Speech-to-Text | Web Speech API (`SpeechRecognition`) — native browser, no API cost |
| Text-to-Speech | Web Speech Synthesis (`SpeechSynthesisUtterance`) — native browser |
| LLM | Claude claude-sonnet-4 via Anthropic Python SDK |
| Transport | FastAPI + JSON REST |

The app **auto-listens** after the assistant finishes speaking, creating a
hands-free back-and-forth conversation loop.

---

## 🔒 Security Notes

- The `ANTHROPIC_API_KEY` is only read server-side — never exposed to the browser
- CORS is set to `*` for development; tighten to your domain in production:
  ```python
  allow_origins=["https://your-domain.com"]
  ```
- No user data is stored — conversation history lives only in the browser session

---

## 📋 Browser Compatibility

| Browser | Voice Input | Voice Output |
|---------|------------|--------------|
| Chrome / Edge | ✅ Full | ✅ |
| Safari | ✅ Full | ✅ |
| Firefox | ⚠️ Limited | ✅ |
| Mobile Chrome | ✅ | ✅ |

Text input fallback is always available for browsers without `SpeechRecognition`.
