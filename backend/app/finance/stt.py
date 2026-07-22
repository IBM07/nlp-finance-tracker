# ==========================================
# finance/stt.py — Deepgram Nova-3 Speech-to-Text
# ==========================================
# Responsible for:
#   1. Forwarding a short recorded audio clip to Deepgram's prerecorded
#      REST API (Nova-3 model) and returning the plain transcript text.
#
# This module does NOT touch the database or trigger any finance action.
# The transcript is handed back to the frontend, which places it into the
# chat input for the user to review and submit via POST /finance/chat.
#
# We call Deepgram's REST endpoint directly with httpx (already a dependency)
# rather than pulling in deepgram-sdk, which is oriented toward the
# live-streaming use case we deliberately are not using.
# ==========================================

import logging

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

DEEPGRAM_URL = "https://api.deepgram.com/v1/listen"
DEEPGRAM_PARAMS = {"model": "nova-3", "smart_format": "true", "punctuate": "true"}
DEEPGRAM_TIMEOUT = 20.0  # seconds — generous for a short voice-command clip


class TranscriptionError(Exception):
    """Raised for any Deepgram failure the route should turn into an HTTP error."""


def transcribe_audio(audio_bytes: bytes, content_type: str) -> str:
    """
    Sends raw audio bytes to Deepgram Nova-3 and returns the transcript string
    (may be empty if no speech was detected — the caller decides how to handle that).

    Raises TranscriptionError on missing config, network failure, a non-200
    response, or an unexpected response shape.
    """
    if not settings.deepgram_api_key:
        logger.critical("DEEPGRAM_API_KEY is not set.")
        raise TranscriptionError("Speech-to-text service is not configured.")

    try:
        resp = httpx.post(
            DEEPGRAM_URL,
            params=DEEPGRAM_PARAMS,
            headers={
                "Authorization": f"Token {settings.deepgram_api_key}",
                "Content-Type": content_type or "audio/webm",
            },
            content=audio_bytes,
            timeout=DEEPGRAM_TIMEOUT,
        )
    except httpx.RequestError as e:
        logger.error("Deepgram network error: %s", e)
        raise TranscriptionError("Could not reach the speech-to-text service.")

    if resp.status_code != 200:
        logger.error("Deepgram API error %s: %s", resp.status_code, resp.text[:500])
        raise TranscriptionError("Speech-to-text service returned an error.")

    data = resp.json()
    try:
        transcript = data["results"]["channels"][0]["alternatives"][0]["transcript"]
    except (KeyError, IndexError, TypeError):
        logger.error("Unexpected Deepgram response shape: %r", data)
        raise TranscriptionError("Speech-to-text service returned an unexpected response.")

    return transcript.strip()
