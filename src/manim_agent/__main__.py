"""CLI 入口：python -m manim_agent

解析命令行参数，调用 pipeline 执行完整的 Claude Agent SDK → TTS → FFmpeg 流程。
"""

import argparse
import asyncio
import logging
import sys

from .dispatcher import _EMOJI
from .pipeline import run_pipeline

logger = logging.getLogger(__name__)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """解析命令行参数。

    Args:
        argv: 参数列表（默认为 sys.argv[1:]）。

    Returns:
        解析后的命名空间。
    """
    parser = argparse.ArgumentParser(
        prog="manim_agent",
        description="AI 驱动的 Manim 数学动画视频自动生成系统",
    )
    parser.add_argument(
        "text",
        help="自然语言描述的视频内容",
    )
    parser.add_argument(
        "-o",
        "--output",
        default="output.mp4",
        help="输出视频文件路径 (default: output.mp4)",
    )
    parser.add_argument(
        "--voice",
        default="female-tianmei",
        help="MiniMax 音色 ID (default: female-tianmei)",
    )
    parser.add_argument(
        "--model",
        default="speech-2.8-hd",
        help="TTS 模型名称 (default: speech-2.8-hd)",
    )
    parser.add_argument(
        "--quality",
        choices=["high", "medium", "low"],
        default="high",
        help="渲染质量 (default: high)",
    )
    parser.add_argument(
        "--no-tts",
        action="store_true",
        help="跳过语音合成，只生成静音视频",
    )
    parser.add_argument(
        "--bgm-enabled",
        action="store_true",
        help="Generate instrumental background music and mix it under the narration.",
    )
    parser.add_argument(
        "--bgm-prompt",
        default=None,
        help="Optional custom prompt for instrumental background music generation.",
    )
    parser.add_argument(
        "--bgm-volume",
        type=float,
        default=0.12,
        help="Background music mix volume from 0.0 to 1.0 (default: 0.12).",
    )
    parser.add_argument(
        "--cwd",
        default=".",
        help="工作目录 (default: 当前目录)",
    )
    parser.add_argument(
        "--prompt-file",
        default=None,
        help="从文件读取自定义提示词",
    )
    parser.add_argument(
        "--max-turns",
        type=int,
        default=80,
        help="Claude 最大交互轮次 (default: 80)",
    )

    parser.add_argument(
        "--target-duration",
        type=int,
        choices=[30, 60, 180, 300],
        default=60,
        help="Target final video duration in seconds (default: 60)",
    )
    parser.add_argument(
        "--render-mode",
        choices=["full", "segments"],
        default="full",
        help="Render delivery mode: full single video or beat segments (default: full).",
    )
    parser.add_argument(
        "--intro-outro",
        action="store_true",
        help="Generate branded intro and/or outro segments.",
    )
    parser.add_argument(
        "--intro-outro-backend",
        choices=["revideo", "manim"],
        default="revideo",
        help="Backend for intro/outro generation (default: revideo).",
    )
    parser.add_argument(
        "--render-review",
        action="store_true",
        help="Enable Phase 3 AI visual review of rendered frames (disabled by default).",
    )

    return parser.parse_args(argv)


async def main() -> None:
    """异步主入口函数。"""
    args = parse_args()

    try:
        _ = await run_pipeline(
            user_text=args.text,
            output_path=args.output,
            voice_id=args.voice,
            model=args.model,
            quality=args.quality,
            no_tts=args.no_tts,
            no_render_review=args.no_render_review,
            bgm_enabled=args.bgm_enabled,
            bgm_prompt=args.bgm_prompt,
            bgm_volume=args.bgm_volume,
            target_duration_seconds=args.target_duration,
            cwd=args.cwd,
            prompt_file=args.prompt_file,
            max_turns=args.max_turns,
            render_mode=args.render_mode,
            intro_outro=args.intro_outro,
            intro_outro_backend=args.intro_outro_backend,
        )
    except KeyboardInterrupt:
        print(f"\n{_EMOJI['cross']} 用户中断")
        sys.exit(130)
    except Exception as e:
        print(f"\n{_EMOJI['cross']} 错误: {e}", file=sys.stderr)
        logger.exception("Pipeline failed with exception:")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
