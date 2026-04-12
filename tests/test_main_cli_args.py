import inspect
from pathlib import Path

import pytest

from manim_agent import __main__ as main_module


class TestParseArgs:
    def test_parse_args_defaults(self):
        args = main_module.parse_args(["解释圆形如何变成正方形"])

        assert args.text == "解释圆形如何变成正方形"
        assert args.output == "output.mp4"
        assert args.voice == "female-tianmei"
        assert args.model == "speech-2.8-hd"
        assert args.quality == "high"
        assert args.no_tts is False
        assert args.cwd == "."
        assert args.prompt_file is None
        assert args.max_turns == 80
        assert args.target_duration == 60

    def test_parse_args_all_options(self):
        args = main_module.parse_args(
            [
                "讲解二叉树",
                "-o",
                "tree.mp4",
                "--voice",
                "male-qn-qingse",
                "--model",
                "speech-02-hd",
                "--quality",
                "low",
                "--no-tts",
                "--max-turns",
                "20",
                "--cwd",
                "/workspace",
                "--prompt-file",
                "custom.txt",
            ]
        )

        assert args.text == "讲解二叉树"
        assert args.output == "tree.mp4"
        assert args.voice == "male-qn-qingse"
        assert args.model == "speech-02-hd"
        assert args.quality == "low"
        assert args.no_tts is True
        assert args.max_turns == 20
        assert args.cwd == "/workspace"
        assert args.prompt_file == "custom.txt"
        assert args.target_duration == 60

    def test_parse_args_requires_text(self):
        with pytest.raises(SystemExit):
            main_module.parse_args([])


class TestStderrHandler:
    def test_stderr_handler_accepts_log_callback(self):
        params = inspect.signature(main_module._stderr_handler).parameters
        assert "log_callback" in params

    def test_stderr_handler_forwards_every_line_to_callback(self):
        forwarded = []

        main_module._stderr_handler("Using model claude-sonnet", log_callback=forwarded.append)
        main_module._stderr_handler("Warning: rate limit approaching", log_callback=forwarded.append)

        assert forwarded == [
            "[CLI] Using model claude-sonnet",
            "[CLI] Warning: rate limit approaching",
        ]


class TestBuildOptions:
    def test_build_options_uses_prompt_file_when_present(self, tmp_path: Path):
        prompt_file = tmp_path / "prompt.txt"
        prompt_file.write_text("Custom prompt", encoding="utf-8")

        options = main_module._build_options(
            cwd=str(tmp_path),
            system_prompt=None,
            prompt_file=str(prompt_file),
            max_turns=10,
        )

        assert options.cwd == str(tmp_path.resolve())
        assert options.system_prompt == "Custom prompt"
        assert options.add_dirs == [str(tmp_path.resolve())]
        assert options.plugins is not None
        assert any(plugin["path"].endswith("plugins\\manim-production") for plugin in options.plugins)
