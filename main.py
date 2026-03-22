import re
import json
import os
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from google import genai
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel


GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
client = genai.Client(api_key=GEMINI_API_KEY)
MODEL = "gemini-2.5-flash"

app = FastAPI(title="VoiceSchedule API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def build_system_prompt() -> str:
    today = datetime.now().strftime("%A, %B %d, %Y")
    return f"""You are VoiceSchedule, a friendly scheduling assistant.
Help the user schedule a calendar event through natural conversation.

Today's date is: {today}

CONVERSATION FLOW:
1. Greet and ask for their name
2. Ask for the meeting title (optional - default to "Meeting")
3. Ask for the preferred date and time
4. Ask for duration (default 60 minutes)
5. Confirm all details
6. Output the event data in the format below

OUTPUT FORMAT (only when you have name + date + time):
<event_data>
{{
  "name": "User's full name",
  "title": "Meeting title",
  "date": "YYYY-MM-DD",
  "time": "HH:MM",
  "duration": 60,
  "description": "Optional description"
}}
</event_data>

RULES:
- Resolve relative dates ("tomorrow", "next Monday") to real YYYY-MM-DD dates
- Only output <event_data> once, when you have name, date, and time
- After outputting event_data say: "I have prepared your event. Click Confirm Booking to add it to your calendar."
- Keep responses short and clear - this is a voice interface
"""


class Message(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    messages: List[Message]

class ChatResponse(BaseModel):
    reply: str
    event_data: Optional[dict] = None


@app.get("/health")
def health():
    return {
        "status": "ok",
        "model": MODEL,
        "api_key_configured": bool(GEMINI_API_KEY),
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    if not GEMINI_API_KEY:
        raise HTTPException(status_code=503, detail="GEMINI_API_KEY is not set on the server.")

    history = []
    for m in req.messages[:-1]:
        history.append(genai.types.Content(
            role="user" if m.role == "user" else "model",
            parts=[genai.types.Part(text=m.content)]
        ))

    last_message = req.messages[-1].content if req.messages else ""

    try:
        chat_session = client.chats.create(
            model=MODEL,
            config=genai.types.GenerateContentConfig(
                system_instruction=build_system_prompt()
            ),
            history=history
        )
        response = chat_session.send_message(last_message)
        full_text = response.text

    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))

    event_data = None
    match = re.search(r"<event_data>(.*?)</event_data>", full_text, re.DOTALL)
    if match:
        try:
            event_data = json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            pass

    clean_reply = re.sub(r"<event_data>.*?</event_data>", "", full_text, flags=re.DOTALL).strip()

    return ChatResponse(reply=clean_reply, event_data=event_data)


STATIC_DIR = Path(__file__).parent / "public"

if STATIC_DIR.exists():
    app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")
else:
    @app.get("/")
    def root():
        return {"message": "VoiceSchedule API is running. Put your frontend in the /public folder."}
