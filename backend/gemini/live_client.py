"""
GeminiLiveClient — wraps the Google GenAI Live API for real-time
speech-to-intent parsing within the InfiniteCanvas orchestration backend.
"""

import asyncio
import json
import logging
from typing import Callable, Awaitable

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are the InfiniteCanvas Reality Conductor — an AI that understands cinematic intent.

Your job: parse voice commands from a viewer watching a film and extract structured cinematic intent.

The film has 4 genres: noir, romcom, horror, scifi
The film has 3 beats: opening (0), confrontation (1), climax (2)

When the user speaks, respond ONLY with a JSON object in this exact format:
{
  "genre": "noir|romcom|horror|scifi|null",
  "action": "change_genre|next_beat|reset|null",
  "confidence": 0.0-1.0,
  "emotional_intensity": 0.0-1.0,
  "feedback": "optional natural language response for user"
}

Examples:
- "make it noir" → {"genre": "noir", "action": "change_genre", "confidence": 0.95, "emotional_intensity": 0.6}
- "she's the villain" → {"genre": "horror", "action": "change_genre", "confidence": 0.75, "emotional_intensity": 0.8}
- "cyberpunk now" → {"genre": "scifi", "action": "change_genre", "confidence": 0.9, "emotional_intensity": 0.9}
- "make it romantic" → {"genre": "romcom", "action": "change_genre", "confidence": 0.85, "emotional_intensity": 0.5}
- "reset" → {"genre": null, "action": "reset", "confidence": 1.0, "emotional_intensity": 0.0}
- "next scene" → {"genre": null, "action": "next_beat", "confidence": 1.0, "emotional_intensity": 0.0}

Only respond with the JSON. No other text.
"""


class GeminiLiveClient:
    """
    Manages a Gemini Live API session for real-time audio → intent parsing.
    Uses google-genai SDK's async live session interface.
    """

    def __init__(self, api_key: str, on_intent: Callable[[dict], None]):
        self.api_key = api_key
        self.on_intent = on_intent
        self._session = None
        self._client = None
        self._recv_task = None
        self._audio_queue: asyncio.Queue = asyncio.Queue()

    async def start(self):
        if not self.api_key:
            logger.warning("GEMINI_API_KEY not set — using mock intent generator")
            self._recv_task = asyncio.create_task(self._mock_recv_loop())
            return

        try:
            from google import genai
            from google.genai import types

            self._client = genai.Client(api_key=self.api_key)
            config = types.LiveConnectConfig(
                response_modalities=["TEXT"],
                system_instruction=SYSTEM_PROMPT,
                speech_config=types.SpeechConfig(
                    voice_activity_detection=types.VoiceActivityDetection(
                        disabled=False,
                    )
                ),
            )
            self._session = await self._client.aio.live.connect(
                model="gemini-2.0-flash-live-001",
                config=config,
            ).__aenter__()
            self._recv_task = asyncio.create_task(self._recv_loop())
            logger.info("Gemini Live session started")
        except Exception as e:
            logger.error(f"Failed to start Gemini Live session: {e}")
            self._recv_task = asyncio.create_task(self._mock_recv_loop())

    async def send_audio(self, pcm_bytes: bytes):
        """Forward raw PCM16 audio to Gemini Live."""
        if self._session:
            try:
                from google.genai import types
                await self._session.send(
                    input=types.LiveClientRealtimeInput(
                        media_chunks=[
                            types.Blob(data=pcm_bytes, mime_type="audio/pcm;rate=16000")
                        ]
                    )
                )
            except Exception as e:
                logger.debug(f"Audio send error: {e}")
        else:
            await self._audio_queue.put(pcm_bytes)

    async def _recv_loop(self):
        """Continuously receive responses from Gemini Live and parse intent."""
        try:
            async for response in self._session.receive():
                if response.text:
                    intent = self._parse_intent(response.text)
                    if intent:
                        self.on_intent(intent)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Recv loop error: {e}")

    async def _mock_recv_loop(self):
        """Fallback mock that silently waits — real intents come from REST /api/intent."""
        logger.info("Running in mock mode (no Gemini API key)")
        try:
            while True:
                await asyncio.sleep(60)
        except asyncio.CancelledError:
            pass

    def _parse_intent(self, text: str) -> dict | None:
        text = text.strip()
        # Strip markdown code fences if present
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:-1]) if len(lines) > 2 else text
        try:
            data = json.loads(text)
            if data.get("confidence", 0) < 0.5:
                return None
            return data
        except json.JSONDecodeError:
            logger.debug(f"Could not parse Gemini response as JSON: {text!r}")
            return None

    async def stop(self):
        if self._recv_task:
            self._recv_task.cancel()
            await asyncio.gather(self._recv_task, return_exceptions=True)
        if self._session:
            try:
                await self._session.__aexit__(None, None, None)
            except Exception:
                pass
        logger.info("Gemini Live session stopped")
