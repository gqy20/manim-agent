"""Tests for manim_agent.music_client."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from manim_agent import music_client


class TestPayload:
    def test_build_payload_defaults_to_music_26(self):
        payload = music_client._build_payload("calm instrumental underscore")
        assert payload["model"] == "music-2.6"
        assert payload["is_instrumental"] is True
        assert payload["output_format"] == "url"

    def test_build_payload_rejects_empty_prompt(self):
        with pytest.raises(ValueError, match="prompt must be a non-empty string"):
            music_client._build_payload("   ")


class TestResponseParsing:
    def test_extract_download_url_prefers_audio_urls(self):
        data = {
            "data": {
                "audio_url": "https://example.com/bgm.mp3",
                "preview_url": "https://example.com/preview.txt",
            }
        }
        assert music_client._extract_download_url(data) == "https://example.com/bgm.mp3"

    def test_duration_parser_accepts_strings(self):
        assert music_client._coerce_duration_ms({"duration_ms": "12345"}) == 12345


@pytest.mark.asyncio
async def test_generate_instrumental_downloads_audio(tmp_path, monkeypatch):
    monkeypatch.setenv("MINIMAX_API_KEY", "test-key")

    post_response = MagicMock()
    post_response.status_code = 200
    post_response.headers = {"content-type": "application/json"}
    post_response.json.return_value = {
        "data": {
            "audio_url": "https://example.com/audio.mp3",
            "duration_ms": 42000,
        }
    }

    download_response = MagicMock()
    download_response.raise_for_status.return_value = None
    download_response.content = b"fake-mp3"

    client = AsyncMock()
    client.__aenter__.return_value = client
    client.__aexit__.return_value = None
    client.post.return_value = post_response
    client.get.return_value = download_response

    with patch("manim_agent.music_client.httpx.AsyncClient", return_value=client):
        result = await music_client.generate_instrumental(
            "calm instrumental underscore",
            output_dir=str(tmp_path),
        )

    assert result.audio_path == str(tmp_path / "bgm.mp3")
    assert result.duration_ms == 42000
    assert Path(result.audio_path).read_bytes() == b"fake-mp3"
