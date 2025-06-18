"""Audio playback utilities using OpenAI's cross platform player."""

import asyncio
import logging
from pathlib import Path
from typing import Any, Union

try:
    from openai import audio as openai_audio
except Exception:  # pragma: no cover - openai might not be installed
    openai_audio = None

logger = logging.getLogger(__name__)


class AudioPlayer:
    """Play audio using the OpenAI helper functions."""

    def __init__(self) -> None:
        logger.info("AudioPlayer initialized")

    async def play(self, source: Union[str, Path, Any]) -> bool:
        """Play audio from a file path or OpenAI response object."""
        if openai_audio is None:
            logger.error("openai.audio module not available")
            return False
        try:
            result = openai_audio.play(str(source)) if isinstance(source, (str, Path)) else openai_audio.play(source)
            if asyncio.iscoroutine(result):
                await result
            return True
        except Exception as exc:  # pragma: no cover - runtime errors
            logger.error(f"Failed to play audio: {exc}")
            return False


_global_player: AudioPlayer | None = None


def get_audio_player() -> AudioPlayer:
    """Return a global ``AudioPlayer`` instance."""
    global _global_player
    if _global_player is None:
        _global_player = AudioPlayer()
    return _global_player


async def play_audio(source: Union[str, Path, Any]) -> bool:
    """Convenience wrapper to play audio via the global player."""
    player = get_audio_player()
    return await player.play(source)
