from moviepy import TextClip, ColorClip, CompositeVideoClip, concatenate_videoclips

WIDTH = 1920
HEIGHT = 1080
FPS = 30
DURATION = 4

slides = [
    "What is Human?",
    "For millions of years...",
    "Humans built tools.",
    "Stone tools.\nWriting.\nComputers.\nAI.",
    "If every capability\ncan be delegated...",
    "What remains human?",
    "Semut Narrative",
]

clips = []

for text in slides:
    background = ColorClip(
        size=(WIDTH, HEIGHT),
        color=(0, 0, 0),
        duration=DURATION,
    )

    title = (
        TextClip(
            text=text,
            font_size=72,
            color="white",
            method="caption",
            size=(1400, None),
            text_align="center",
        )
        .with_duration(DURATION)
        .with_position("center")
    )

    clip = CompositeVideoClip(
        [background, title],
        size=(WIDTH, HEIGHT),
    ).with_duration(DURATION)

    clips.append(clip)

video = concatenate_videoclips(clips, method="compose")

video.write_videofile(
    "output/what_is_human.mp4",
    fps=FPS,
    codec="libx264",
    audio=False,
)
