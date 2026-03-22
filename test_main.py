"""
Tests for the VoiceSchedule FastAPI backend.

Run with:
    pytest tests/ -v

For integration tests that call the real Anthropic API set:
    ANTHROPIC_API_KEY=sk-ant-... pytest tests/ -v
"""

import os
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

# Add backend to path
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from backend.main import app

client = TestClient(app)


# ── /health ──────────────────────────────────────────────────────────────────

class TestHealth:
    def test_health_returns_200(self):
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_schema(self):
        data = client.get("/health").json()
        assert "status" in data
        assert "model" in data
        assert "api_key_configured" in data
        assert "timestamp" in data

    def test_health_status_ok(self):
        data = client.get("/health").json()
        assert data["status"] == "ok"

    def test_health_model_name(self):
        data = client.get("/health").json()
        assert "claude" in data["model"]


# ── /chat  ────────────────────────────────────────────────────────────────────

MOCK_REPLY = "Great to meet you, Alex! What date and time works for your meeting?"

def _make_mock_response(text: str):
    """Build a mock Anthropic response object."""
    mock = MagicMock()
    mock.content = [MagicMock(text=text)]
    return mock


class TestChatBasic:
    @patch("backend.main.client")
    def test_chat_returns_200(self, mock_client):
        mock_client.messages.create.return_value = _make_mock_response(MOCK_REPLY)
        response = client.post("/chat", json={
            "messages": [{"role": "user", "content": "Hi, my name is Alex"}]
        })
        assert response.status_code == 200

    @patch("backend.main.client")
    def test_chat_reply_field_present(self, mock_client):
        mock_client.messages.create.return_value = _make_mock_response(MOCK_REPLY)
        data = client.post("/chat", json={
            "messages": [{"role": "user", "content": "Hi, my name is Alex"}]
        }).json()
        assert "reply" in data
        assert "event_data" in data

    @patch("backend.main.client")
    def test_chat_no_event_data_initially(self, mock_client):
        mock_client.messages.create.return_value = _make_mock_response(MOCK_REPLY)
        data = client.post("/chat", json={
            "messages": [{"role": "user", "content": "Hello"}]
        }).json()
        assert data["event_data"] is None

    @patch("backend.main.client")
    def test_chat_passes_full_history(self, mock_client):
        mock_client.messages.create.return_value = _make_mock_response(MOCK_REPLY)
        messages = [
            {"role": "user", "content": "Hi"},
            {"role": "assistant", "content": "Hello! What's your name?"},
            {"role": "user", "content": "I'm Alex"},
        ]
        client.post("/chat", json={"messages": messages})
        call_args = mock_client.messages.create.call_args
        sent_messages = call_args.kwargs["messages"]
        assert len(sent_messages) == 3

    @patch("backend.main.client")
    def test_chat_empty_messages_still_works(self, mock_client):
        mock_client.messages.create.return_value = _make_mock_response("Hello! How can I help?")
        response = client.post("/chat", json={"messages": []})
        assert response.status_code == 200


class TestChatEventExtraction:
    EVENT_RESPONSE = """Great! I've prepared your event. Click Confirm Booking to add it to your calendar.

<event_data>
{
  "name": "Alex",
  "title": "Team Standup",
  "date": "2026-03-20",
  "time": "09:00",
  "duration": 30,
  "description": "Daily standup"
}
</event_data>"""

    @patch("backend.main.client")
    def test_event_data_extracted(self, mock_client):
        mock_client.messages.create.return_value = _make_mock_response(self.EVENT_RESPONSE)
        data = client.post("/chat", json={
            "messages": [{"role": "user", "content": "Tomorrow at 9am, 30 minutes"}]
        }).json()
        assert data["event_data"] is not None
        assert data["event_data"]["name"] == "Alex"
        assert data["event_data"]["title"] == "Team Standup"
        assert data["event_data"]["date"] == "2026-03-20"
        assert data["event_data"]["time"] == "09:00"
        assert data["event_data"]["duration"] == 30

    @patch("backend.main.client")
    def test_event_xml_stripped_from_reply(self, mock_client):
        mock_client.messages.create.return_value = _make_mock_response(self.EVENT_RESPONSE)
        data = client.post("/chat", json={
            "messages": [{"role": "user", "content": "Tomorrow at 9am"}]
        }).json()
        assert "<event_data>" not in data["reply"]
        assert "Confirm Booking" in data["reply"]

    @patch("backend.main.client")
    def test_malformed_event_json_doesnt_crash(self, mock_client):
        bad_response = "Here is your event. <event_data>{ bad json !! }</event_data>"
        mock_client.messages.create.return_value = _make_mock_response(bad_response)
        response = client.post("/chat", json={
            "messages": [{"role": "user", "content": "test"}]
        })
        assert response.status_code == 200
        assert response.json()["event_data"] is None


class TestChatErrors:
    @patch("backend.main.ANTHROPIC_API_KEY", "")
    def test_missing_api_key_returns_503(self):
        response = client.post("/chat", json={
            "messages": [{"role": "user", "content": "Hello"}]
        })
        assert response.status_code == 503

    @patch("backend.main.client")
    def test_anthropic_auth_error_returns_401(self, mock_client):
        import anthropic
        mock_client.messages.create.side_effect = anthropic.AuthenticationError(
            message="Invalid key", response=MagicMock(status_code=401), body={}
        )
        response = client.post("/chat", json={
            "messages": [{"role": "user", "content": "Hello"}]
        })
        assert response.status_code == 401

    @patch("backend.main.client")
    def test_rate_limit_returns_429(self, mock_client):
        import anthropic
        mock_client.messages.create.side_effect = anthropic.RateLimitError(
            message="Rate limited", response=MagicMock(status_code=429), body={}
        )
        response = client.post("/chat", json={
            "messages": [{"role": "user", "content": "Hello"}]
        })
        assert response.status_code == 429


# ── Integration test (only runs when real key is set) ────────────────────────

@pytest.mark.skipif(
    not os.environ.get("ANTHROPIC_API_KEY", "").startswith("sk-"),
    reason="Skipped: real ANTHROPIC_API_KEY not set",
)
class TestIntegration:
    def test_real_greeting(self):
        response = client.post("/chat", json={
            "messages": [{"role": "user", "content": "Hello, I want to schedule a meeting"}]
        })
        assert response.status_code == 200
        data = response.json()
        assert len(data["reply"]) > 10
        assert data["event_data"] is None   # not enough info yet
