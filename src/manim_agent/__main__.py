"""CLI 入口：python -m manim_agent

解析命令行参数，编排 Claude Agent SDK → TTS → FFmpeg 的完整 pipeline。
"""

import argparse
import asyncio
import sys
from pathlib import Path

from claude_agent_sdk import query, ClaudeAgentOptions

from . import prompts
from . import tts_client
from . import video_builder


# ── CLI 参数解析 ──────────────────────────────────────────────


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
        "-o", "--output",
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
        default=50,
        help="Claude 最大交互轮次 (default: 50)",
    )

    return parser.parse_args(argv)


# ── 结果提取 ──────────────────────────────────────────────────


def extract_result(text: str) -> dict[str, str | None]:
    """从 Claude 输出文本中提取结构化结果标记。

    Args:
        text: Claude 输出的文本内容（可能包含多行）。

    Returns:
        包含 video_output_path, scene_file, scene_class 的字典。
        未找到的值为 None。
    """
    result = {
        "video_output_path": None,
        "scene_file": None,
        "scene_class": None,
    }

    # 取最后一个有效的 VIDEO_OUTPUT（Claude 可能多次输出）
    last_video_output = None
    for line in text.splitlines():
        if line.startswith("VIDEO_OUTPUT:"):
            last_video_output = line.split(":", 1)[1].strip()
        elif line.startswith("SCENE_FILE:"):
            result["scene_file"] = line.split(":", 1)[1].strip()
        elif line.startswith("SCENE_CLASS:"):
            result["scene_class"] = line.split(":", 1)[1].strip()

    result["video_output_path"] = last_video_output
    return result


# ── Pipeline 编排 ─────────────────────────────────────────────


async def run_pipeline(
    user_text: str,
    output_path: str,
    voice_id: str = "female-tianmei",
    model: str = "speech-2.8-hd",
    quality: str = "high",
    no_tts: bool = False,
    cwd: str = ".",
    prompt_file: str | None = None,
    max_turns: int = 50,
) -> str:
    """执行完整的视频生成 pipeline。

    流程：
    1. 构建提示词
    2. 调用 Claude Agent SDK (query)
    3. 从响应中提取 VIDEO_OUTPUT 路径
    4. （可选）TTS 语音合成
    5. （可选）FFmpeg 视频合成
    6. 返回最终视频路径

    Args:
        user_text: 用户输入的自然语言描述。
        output_path: 输出视频路径。
        voice_id: TTS 音色 ID。
        model: TTS 模型。
        quality: 渲染质量。
        no_tts: 是否跳过 TTS。
        cwd: 工作目录。
        prompt_file: 自定义提示词文件路径。
        max_turns: Claude 最大交互轮次。

    Returns:
        最终视频文件路径。

    Raises:
        RuntimeError: Claude 未输出 VIDEO_OUTPUT 标记。
    """
    # 1. 构建提示词
    if prompt_file and Path(prompt_file).exists():
        system_prompt = Path(prompt_file).read_text(encoding="utf-8")
    else:
        full_prompt = prompts.get_prompt(user_text, quality=quality)
        # get_prompt 返回的是完整 prompt（system + user），
        # 这里需要拆分或直接作为 user prompt 使用
        # 实际上 query() 接收的是 user_prompt，system_prompt 通过 options 传入
        system_prompt = prompts.SYSTEM_PROMPT
        user_prompt = user_text

    # 2. 调用 Claude Agent SDK
    options = ClaudeAgentOptions(
        cwd=cwd,
        system_prompt=system_prompt,
        permission_mode="acceptEdits",
        max_turns=max_turns,
    )

    collected_text = ""
    async for message in query(prompt=user_prompt, options=options):
        if hasattr(message, "content"):
            for block in message.content:
                if hasattr(block, "text") and isinstance(block.text, str):
                    collected_text += block.text + "\n"

    # 3. 提取结果
    result = extract_result(collected_text)
    video_output = result["video_output_path"]

    if not video_output:
        raise RuntimeError(
            "Claude did not produce a VIDEO_OUTPUT marker. "
            "The agent may have failed to render the scene."
        )

    # 4-5. TTS + FFmpeg（可选）
    if no_tts:
        return video_output

    # 使用 Claude 输出内容作为 TTS 脚本
    tts_result = await tts_client.synthesize(
        text=user_text,
        voice_id=voice_id,
        model=model,
        output_dir=str(Path(output_path).parent),
    )

    final_video = await video_builder.build_final_video(
        video_path=video_output,
        audio_path=tts_result.audio_path,
        subtitle_path=tts_result.subtitle_path,
        output_path=output_path,
    )

    return final_video


# ── 入口点 ────────────────────────────────────────────────────


async def main() -> None:
    """异步主入口函数。"""
    args = parse_args()

    try:
        output = await run_pipeline(
            user_text=args.text,
            output_path=args.output,
            voice_id=args.voice,
            model=args.model,
            quality=args.quality,
            no_tts=args.no_tts,
            cwd=args.cwd,
            prompt_file=args.prompt_file,
            max_turns=args.max_turns,
        )
        print(f"\n✅ 视频生成完成: {output}")
    except KeyboardInterrupt:
        print("\n⚠️ 用户中断")
        sys.exit(130)
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
