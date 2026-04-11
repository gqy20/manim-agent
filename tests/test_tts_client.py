"""Tests for manim_agent.tts_client module."""

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from manim_agent import tts_client


# ── Fixtures ───────────────────────────────────────────────────


@pytest.fixture
def mock_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """设置 MINIMAX_API_KEY 环境变量。"""
    monkeypatch.setenv("MINIMAX_API_KEY", "test-api-key-12345")


@pytest.fixture
def sample_tts_result(tmp_path) -> tts_client.TTSResult:
    """生成示例 TTSResult。"""
    audio = tmp_path / "audio.mp3"
    subtitle = tmp_path / "subtitle.srt"
    extra = tmp_path / "extra_info.json"
    audio.touch()
    subtitle.touch()
    extra.write_text(json.dumps({"audio_length": 5000}))
    return tts_client.TTSResult(
        audio_path=str(audio),
        subtitle_path=str(subtitle),
        extra_info_path=str(extra),
        duration_ms=5000,
        word_count=100,
        usage_characters=120,
    )


# ── TTSResult Dataclass ────────────────────────────────────────


class TestTTSResult:
    def test_fields_exist(self, sample_tts_result):
        """TTSResult 包含所有必需字段。"""
        assert hasattr(sample_tts_result, "audio_path")
        assert hasattr(sample_tts_result, "subtitle_path")
        assert hasattr(sample_tts_result, "extra_info_path")
        assert hasattr(sample_tts_result, "duration_ms")
        assert hasattr(sample_tts_result, "word_count")
        assert hasattr(sample_tts_result, "usage_characters")

    def test_field_types(self, sample_tts_result):
        """字段类型正确。"""
        assert isinstance(sample_tts_result.audio_path, str)
        assert isinstance(sample_tts_result.subtitle_path, str)
        assert isinstance(sample_tts_result.extra_info_path, str)
        assert isinstance(sample_tts_result.duration_ms, int)
        assert isinstance(sample_tts_result.word_count, int)
        assert isinstance(sample_tts_result.usage_characters, int)


# ── API Key 校验 ──────────────────────────────────────────────


class TestApiKeyCheck:
    def test_missing_api_key_raises(self, monkeypatch: pytest.MonkeyPatch):
        """无 MINIMAX_API_KEY 环境变量时抛异常。"""
        monkeypatch.delenv("MINIMAX_API_KEY", raising=False)
        with pytest.raises(RuntimeError, match="API Key"):
            tts_client._check_api_key()

    def test_empty_api_key_raises(self, monkeypatch: pytest.MonkeyPatch):
        """空 API Key 抛异常。"""
        monkeypatch.setenv("MINIMAX_API_KEY", "")
        with pytest.raises(RuntimeError, match="API Key"):
            tts_client._check_api_key()

    def test_valid_api_key_passes(self, mock_env):
        """有效的 API Key 不抛异常。"""
        tts_client._check_api_key()  # 不应抛出


# ── 请求体构建 ────────────────────────────────────────────────


class TestBuildPayload:
    def test_default_payload_structure(self, mock_env):
        """默认请求体结构正确。"""
        payload = tts_client._build_payload("你好世界")
        assert payload["model"] == "speech-2.8-hd"
        assert payload["text"] == "你好世界"
        assert payload["voice_setting"]["voice_id"] == "female-tianmei"
        assert payload["voice_setting"]["speed"] == 1.0
        assert payload["audio_setting"]["format"] == "mp3"

    def test_custom_voice_id(self, mock_env):
        """自定义 voice_id 生效。"""
        payload = tts_client._build_payload(
            "测试", voice_id="male-qn-qingse"
        )
        assert payload["voice_setting"]["voice_id"] == "male-qn-qingse"

    def test_custom_speed(self, mock_env):
        """自定义 speed 生效。"""
        payload = tts_client._build_payload("测试", speed=1.5)
        assert payload["voice_setting"]["speed"] == 1.5

    def test_empty_text_raises(self, mock_env):
        """空文本抛 ValueError。"""
        with pytest.raises(ValueError, match="text"):
            tts_client._build_payload("")

    def test_whitespace_only_text_raises(self, mock_env):
        """纯空白文本抛 ValueError。"""
        with pytest.raises(ValueError, match="text"):
            tts_client._build_payload("   ")


# ── 任务创建（函数级 mock） ────────────────────────────────────


class TestCreateTask:
    @staticmethod
    def _mock_json_resp(payload, status_code: int = 200, content_type: str = "application/json"):
        mock_resp = MagicMock()
        mock_resp.status_code = status_code
        mock_resp.headers = {"content-type": content_type}
        mock_resp.text = json.dumps(payload)
        mock_resp.json.return_value = payload
        return mock_resp

    @pytest.mark.asyncio
    async def test_success_returns_task_info(self, mock_env):
        """成功创建任务返回 task_id 和 file_id。"""
        mock_resp = self._mock_json_resp({
            "base_resp": {"status_code": 0},
            "data": {
                "task_id": "task-001",
                "file_id": "file-audio",
                "file_id_subtitle": "file-sub",
                "file_id_extra": "file-extra",
            },
        })

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_resp
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("manim_agent.tts_client.httpx.AsyncClient", return_value=mock_client):
            result = await tts_client._create_task("test text", {})

        assert result["task_id"] == "task-001"
        assert result["file_id"] == "file-audio"
        assert result["file_id_subtitle"] == "file-sub"

    @pytest.mark.asyncio
    async def test_api_error_raises(self, mock_env):
        """API 返回错误时抛 RuntimeError。"""
        mock_resp = self._mock_json_resp({
            "base_resp": {"status_code": 40004, "status_msg": "Invalid API Key"},
        })

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_resp
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("manim_agent.tts_client.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(RuntimeError, match="TTS task creation failed"):
                await tts_client._create_task("test text", {})


# ── 任务轮询（函数级 mock） ────────────────────────────────────


class TestPollTask:
    @staticmethod
    def _mock_json_resp(payload, status_code: int = 200, content_type: str = "application/json"):
        mock_resp = MagicMock()
        mock_resp.status_code = status_code
        mock_resp.headers = {"content-type": content_type}
        mock_resp.text = json.dumps(payload)
        mock_resp.json.return_value = payload
        return mock_resp

    @staticmethod
    def _mock_non_json(status_code: int = 404, text: str = "404 Page not found"):
        mock_resp = MagicMock()
        mock_resp.status_code = status_code
        mock_resp.headers = {"content-type": "text/plain"}
        mock_resp.text = text
        mock_resp.json.side_effect = json.JSONDecodeError("invalid", text, 0)
        return mock_resp

    @pytest.mark.asyncio
    async def test_success_on_first_try(self, mock_env):
        """首次轮询即成功。"""
        mock_resp = self._mock_json_resp({
            "base_resp": {"status_code": 0},
            "data": {"task_status": "Success", "audio_length": 5000, "word_count": 100},
        })

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_resp
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("manim_agent.tts_client.httpx.AsyncClient", return_value=mock_client):
            data = await tts_client._poll_task("task-001")

        assert data["task_status"] == "Success"
        assert data["audio_length"] == 5000

    @pytest.mark.asyncio
    async def test_timeout_raises(self, mock_env):
        """轮询超时抛 TimeoutError。"""
        mock_resp = self._mock_json_resp({
            "base_resp": {"status_code": 0},
            "data": {"task_status": "Processing"},
        })

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_resp
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("manim_agent.tts_client.httpx.AsyncClient", return_value=mock_client),
            patch("manim_agent.tts_client.POLL_TIMEOUT", 0.01),
            patch("manim_agent.tts_client.POLL_INTERVAL", 0.001),
        ):
            with pytest.raises(TimeoutError, match="TTS polling timeout"):
                await tts_client._poll_task("task-001")

    @pytest.mark.asyncio
    async def test_task_failed_raises(self, mock_env):
        """任务失败抛 RuntimeError。"""
        mock_resp = self._mock_json_resp({
            "base_resp": {"status_code": 0},
            "data": {"task_status": "Failed", "error_message": "invalid chars"},
        })

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_resp
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("manim_agent.tts_client.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(RuntimeError, match="TTS task failed"):
                await tts_client._poll_task("task-001")


# ── 文件下载（函数级 mock） ────────────────────────────────────


    @pytest.mark.asyncio
    async def test_legacy_flat_payload(self, mock_env):
        """支持顶层 status/task_status。"""
        mock_resp = self._mock_json_resp({
            "status_code": 0,
            "status": "success",
            "audio_length": 3000,
            "word_count": 200,
        })

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_resp
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("manim_agent.tts_client.httpx.AsyncClient", return_value=mock_client):
            data = await tts_client._poll_task("task-001")

        assert data["status"] == "success"
        assert data["audio_length"] == 3000

    @pytest.mark.asyncio
    async def test_query_path_fallback(self, mock_env):
        """旧查询地址 404 时回退到历史地址。"""
        legacy_404 = self._mock_non_json()
        modern_ok = self._mock_json_resp({
            "base_resp": {"status_code": 0},
            "status": "Success",
            "audio_length": 1200,
        })

        mock_client = AsyncMock()
        mock_client.get.side_effect = [legacy_404, modern_ok]
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("manim_agent.tts_client.httpx.AsyncClient", return_value=mock_client):
            data = await tts_client._poll_task("task-001")

        assert data["audio_length"] == 1200
        assert mock_client.get.call_count == 2

    @pytest.mark.asyncio
    async def test_empty_task_id_raises(self, mock_env):
        """空 task_id 直接报错。"""
        with pytest.raises(RuntimeError, match="task_id is empty"):
            await tts_client._poll_task("   ")


class TestDownloadFiles:
    @pytest.mark.asyncio
    async def test_download_success(self, mock_env, tmp_path):
        """成功下载所有文件。"""
        file_ids = {"audio": "f-audio", "subtitle": "f-sub", "extra": "f-extra"}
        output_dir = str(tmp_path / "out")

        # Mock _download_file 以避免真实 httpx 调用
        async def fake_download(fid, path, api_key, base_url):
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            Path(path).write_bytes(b"fake")

        with patch("manim_agent.tts_client._download_file", side_effect=fake_download):
            paths = await tts_client._download_files(file_ids, output_dir)

        assert "audio" in paths
        assert "subtitle" in paths
        assert "extra" in paths
        # 验证文件确实被创建了
        assert Path(paths["audio"]).exists()

    @pytest.mark.asyncio
    async def test_download_propagates_error(self, mock_env, tmp_path):
        """_download_file 失败时异常向上传播。"""
        file_ids = {"audio": "f-audio", "subtitle": "f-sub", "extra": "f-extra"}

        async def always_fail(fid, path, api_key, base_url):
            raise RuntimeError("network error")

        with (
            patch("manim_agent.tts_client._download_file", side_effect=always_fail),
            pytest.raises(RuntimeError, match="network error"),
        ):
            await tts_client._download_files(file_ids, str(tmp_path / "out"))


# ── synthesize 全流程 ─────────────────────────────────────────


class TestSynthesize:
    @pytest.mark.asyncio
    async def test_full_flow_mocked(self, mock_env, tmp_path):
        """全链路 mock 测试：创建→轮询→下载→返回结果。"""
        output_dir = str(tmp_path / "tts_output")

        with (
            patch("manim_agent.tts_client._check_api_key"),
            patch("manim_agent.tts_client._create_task", new_callable=AsyncMock) as mock_create,
            patch("manim_agent.tts_client._poll_task", new_callable=AsyncMock) as mock_poll,
            patch("manim_agent.tts_client._download_files", new_callable=AsyncMock) as mock_download,
        ):
            mock_create.return_value = {
                "task_id": "t-001",
                "file_id": "f-audio",
                "file_id_subtitle": "f-sub",
                "file_id_extra": "f-extra",
            }
            mock_poll.return_value = {
                "task_status": "Success",
                "audio_length": 8000,
                "word_count": 150,
                "usage_characters": 180,
            }
            mock_download.return_value = {
                "audio": f"{output_dir}/audio.mp3",
                "subtitle": f"{output_dir}/subtitle.srt",
                "extra": f"{output_dir}/extra_info.json",
            }

            result = await tts_client.synthesize(
                "这是一段测试文本",
                output_dir=output_dir,
            )

            assert isinstance(result, tts_client.TTSResult)
            assert result.audio_path.endswith("audio.mp3")
            assert result.subtitle_path.endswith("subtitle.srt")
            assert result.duration_ms == 8000
            assert result.word_count == 150
            mock_create.assert_awaited_once()
            mock_poll.assert_awaited_once_with("t-001")
            mock_download.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_empty_text_raises(self, mock_env):
        """空文本直接抛异常（在 payload 构建阶段）。"""
        with pytest.raises(ValueError):
            await tts_client.synthesize("")


class TestIdentifierNormalization:
    @pytest.mark.asyncio
    async def test_create_task_normalizes_numeric_identifiers(self, mock_env):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.headers = {"content-type": "application/json"}
        mock_resp.text = json.dumps({
            "base_resp": {"status_code": 0},
            "data": {
                "task_id": 12345,
                "file_id": 67890,
                "file_id_subtitle": 67891,
                "file_id_extra": 67892,
            },
        })
        mock_resp.json.return_value = json.loads(mock_resp.text)

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_resp
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("manim_agent.tts_client.httpx.AsyncClient", return_value=mock_client):
            result = await tts_client._create_task("test text", {})

        assert result["task_id"] == "12345"
        assert result["file_id"] == "67890"
        assert result["file_id_subtitle"] == "67891"
        assert result["file_id_extra"] == "67892"

    @pytest.mark.asyncio
    async def test_poll_task_accepts_numeric_task_id(self, mock_env):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.headers = {"content-type": "application/json"}
        mock_resp.text = json.dumps({
            "base_resp": {"status_code": 0},
            "data": {"task_status": "Success", "audio_length": 5000, "word_count": 100},
        })
        mock_resp.json.return_value = json.loads(mock_resp.text)

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_resp
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("manim_agent.tts_client.httpx.AsyncClient", return_value=mock_client):
            data = await tts_client._poll_task(12345)

        assert data["task_status"] == "Success"
        assert mock_client.get.call_args.kwargs["params"]["task_id"] == "12345"
