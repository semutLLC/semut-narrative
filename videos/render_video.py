from __future__ import annotations

import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "essays" / "01-what-is-human" / "script.md"
OUTPUT_PATH = ROOT / "videos" / "output" / "what_is_human.mp4"
LOCAL_DEPS = ROOT / ".deps"

if LOCAL_DEPS.exists():
    sys.path.insert(0, str(LOCAL_DEPS))


@dataclass(frozen=True)
class Theme:
    width: int = 1920
    height: int = 1080
    fps: int = 30
    background_color: tuple[int, int, int] = (0, 0, 0)
    text_color: str = "white"
    font_size: int = 72
    text_box_width: int = 1400
    line_spacing: int = 28
    fade_seconds: float = 0.75
    font_path: str = "C:/Windows/Fonts/arial.ttf"


@dataclass(frozen=True)
class Scene:
    duration: float
    text: str


def parse_scenes(script_path: Path) -> list[Scene]:
    content = script_path.read_text(encoding="utf-8")
    chunks = re.split(r"(?m)^##\s+Scene\b.*$", content)
    scenes: list[Scene] = []

    for chunk in chunks[1:]:
        duration_match = re.search(r"(?m)^Duration:\s*([0-9]+(?:\.[0-9]+)?)\s*$", chunk)
        if not duration_match:
            raise ValueError("Scene is missing a Duration: line.")

        duration = float(duration_match.group(1))
        body = chunk[duration_match.end() :].replace("---", "").strip()
        if not body:
            raise ValueError("Scene is missing text.")

        scenes.append(Scene(duration=duration, text=body))

    if not scenes:
        raise ValueError(f"No scenes found in {script_path}.")

    return scenes


def load_ffmpeg_exe() -> str:
    try:
        from imageio_ffmpeg import get_ffmpeg_exe
    except ModuleNotFoundError as exc:
        raise ModuleNotFoundError(
            "imageio-ffmpeg is required to render video. Install it with `pip install imageio-ffmpeg`."
        ) from exc

    return get_ffmpeg_exe()


def render_text_image(text: str, theme: Theme):
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont

    image = Image.new("RGBA", (theme.width, theme.height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    try:
        font = ImageFont.truetype(theme.font_path, theme.font_size)
    except OSError:
        font = ImageFont.load_default(size=theme.font_size)

    def wrap_line(line: str) -> list[str]:
        words = line.split()
        wrapped: list[str] = []
        current = ""

        for word in words:
            candidate = f"{current} {word}".strip()
            bbox = draw.textbbox((0, 0), candidate, font=font)
            if bbox[2] - bbox[0] <= theme.text_box_width or not current:
                current = candidate
            else:
                wrapped.append(current)
                current = word

        if current:
            wrapped.append(current)

        return wrapped

    lines: list[str] = []
    for paragraph in text.splitlines():
        if not paragraph:
            lines.append("")
            continue

        lines.extend(wrap_line(paragraph))

    line_heights = [
        draw.textbbox((0, 0), line or " ", font=font)[3]
        - draw.textbbox((0, 0), line or " ", font=font)[1]
        for line in lines
    ]
    total_height = sum(line_heights) + theme.line_spacing * max(len(lines) - 1, 0)
    y = (theme.height - total_height) / 2

    for line, line_height in zip(lines, line_heights):
        if line:
            bbox = draw.textbbox((0, 0), line, font=font)
            text_width = bbox[2] - bbox[0]
            x = (theme.width - text_width) / 2
            draw.text((x, y), line, fill=theme.text_color, font=font)
        y += line_height + theme.line_spacing

    return np.array(image)


def render_scene_clip(
    ffmpeg_exe: str,
    scene: Scene,
    theme: Theme,
    image_path: Path,
    clip_path: Path,
) -> None:
    from PIL import Image

    fade = min(theme.fade_seconds, scene.duration / 2)
    fade_out_start = max(0, scene.duration - fade)
    color = "0x%02x%02x%02x" % theme.background_color

    Image.fromarray(render_text_image(scene.text, theme)).save(image_path)

    command = [
        ffmpeg_exe,
        "-y",
        "-loglevel",
        "error",
        "-f",
        "lavfi",
        "-i",
        f"color=c={color}:s={theme.width}x{theme.height}:r={theme.fps}:d={scene.duration}",
        "-loop",
        "1",
        "-i",
        str(image_path),
        "-filter_complex",
        (
            f"[1:v]format=rgba,fade=t=in:st=0:d={fade}:alpha=1,"
            f"fade=t=out:st={fade_out_start}:d={fade}:alpha=1[text];"
            "[0:v][text]overlay=0:0:format=auto"
        ),
        "-t",
        str(scene.duration),
        "-an",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        str(clip_path),
    ]
    subprocess.run(command, check=True)


def concatenate_scene_clips(ffmpeg_exe: str, clip_paths: list[Path], output_path: Path) -> None:
    concat_path = clip_paths[0].parent / "concat.txt"
    concat_path.write_text(
        "".join(f"file '{path.as_posix()}'\n" for path in clip_paths),
        encoding="utf-8",
    )

    command = [
        ffmpeg_exe,
        "-y",
        "-loglevel",
        "error",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(concat_path),
        "-c",
        "copy",
        "-movflags",
        "+faststart",
        str(output_path),
    ]
    subprocess.run(command, check=True)


def render_video(
    script_path: Path = SCRIPT_PATH,
    output_path: Path = OUTPUT_PATH,
    theme: Theme | None = None,
) -> None:
    ffmpeg_exe = load_ffmpeg_exe()
    active_theme = theme or Theme()
    scenes = parse_scenes(script_path)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="render-", dir=output_path.parent) as temp_dir:
        temp_path = Path(temp_dir)
        clip_paths: list[Path] = []

        for index, scene in enumerate(scenes, start=1):
            image_path = temp_path / f"scene-{index:02d}.png"
            clip_path = temp_path / f"scene-{index:02d}.mp4"
            render_scene_clip(ffmpeg_exe, scene, active_theme, image_path, clip_path)
            clip_paths.append(clip_path)

        concatenate_scene_clips(ffmpeg_exe, clip_paths, output_path)


if __name__ == "__main__":
    render_video()
