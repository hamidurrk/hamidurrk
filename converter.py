"""Convert videos in media/source into lightweight GIFs in media/gif using ffmpeg.

Per-video clip settings (start/end/fps/width) are read from media/clips.json,
which the local clipper tool (clipper/server.py) writes.
"""
import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SOURCE_DIR = ROOT / "media" / "source"
GIF_DIR = ROOT / "media" / "gif"
CLIPS_FILE = ROOT / "media" / "clips.json"
VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".webm"}

DEFAULTS = {"start": 0.0, "duration": 6.0, "fps": 10, "width": 320, "colors": 128, "denoise": False}
WARN_BYTES = 1024 * 1024


def list_videos() -> list[Path]:
    return sorted(p for p in SOURCE_DIR.glob("*") if p.suffix.lower() in VIDEO_EXTS)


def load_clips() -> dict:
    try:
        return json.loads(CLIPS_FILE.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_clips(clips: dict) -> None:
    CLIPS_FILE.write_text(json.dumps(clips, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def settings_for(stem: str, clips: dict | None = None, defaults: dict | None = None) -> dict:
    """Effective settings for a video: clips.json entry over defaults."""
    base = dict(defaults or DEFAULTS)
    clip = (clips if clips is not None else load_clips()).get(stem, {})
    start = float(clip.get("start", base["start"]))
    duration = float(clip["end"]) - start if "end" in clip else base["duration"]
    return {
        "start": start,
        "duration": max(duration, 0.1),
        "fps": int(clip.get("fps", base["fps"])),
        "width": int(clip.get("width", base["width"])),
        "colors": int(clip.get("colors", base.get("colors", 128))),
        "denoise": bool(clip.get("denoise", base.get("denoise", False))),
    }


def convert(ffmpeg: str, src: Path, dst: Path, start: float, duration: float,
            fps: int, width: int, colors: int = 128, denoise: bool = False) -> bool:
    # denoise helps a lot with camera footage, where sensor noise changes every pixel each frame
    clean = "hqdn3d=4:3:6:6," if denoise else ""
    filters = (
        f"fps={fps},scale={width}:-1:flags=lanczos,{clean}split[s0][s1];"
        f"[s0]palettegen=max_colors={max(2, min(colors, 256))}:stats_mode=diff[p];"
        "[s1][p]paletteuse=dither=bayer:bayer_scale=5:diff_mode=rectangle"
    )
    cmd = [
        ffmpeg, "-y", "-loglevel", "error",
        "-ss", f"{start:.3f}", "-t", f"{duration:.3f}", "-i", str(src),
        "-vf", filters, "-loop", "0", str(dst),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(result.stderr.strip(), file=sys.stderr)
        dst.unlink(missing_ok=True)
        return False
    return True


def human(n: int) -> str:
    return f"{n / 1024 / 1024:.2f} MB" if n >= WARN_BYTES else f"{n / 1024:.0f} KB"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("names", nargs="*", help="only convert these videos (file stem, e.g. tethr)")
    parser.add_argument("--fps", type=int, default=DEFAULTS["fps"], help="default frame rate (10)")
    parser.add_argument("--width", type=int, default=DEFAULTS["width"], help="default width in px (320)")
    parser.add_argument("--duration", type=float, default=DEFAULTS["duration"], help="default clip length in s (6)")
    parser.add_argument("--force", action="store_true", help="overwrite existing GIFs")
    args = parser.parse_args()

    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        print("Error: ffmpeg not found on PATH.", file=sys.stderr)
        return 1

    GIF_DIR.mkdir(parents=True, exist_ok=True)
    videos = list_videos()
    if args.names:
        wanted = set(args.names)
        videos = [v for v in videos if v.stem in wanted]
        for missing in wanted - {v.stem for v in videos}:
            print(f"Warning: no video named '{missing}' in {SOURCE_DIR}")
    if not videos:
        print(f"No videos to convert in {SOURCE_DIR}")
        return 0

    clips = load_clips()
    defaults = {**DEFAULTS, "duration": args.duration, "fps": args.fps, "width": args.width}
    done = skipped = failed = 0
    for video in videos:
        gif = GIF_DIR / f"{video.stem}.gif"
        if gif.exists() and not args.force:
            print(f"skip     {video.name} (gif exists)")
            skipped += 1
            continue
        s = settings_for(video.stem, clips, defaults)
        if convert(ffmpeg, video, gif, **s):
            size = gif.stat().st_size
            warn = "  <-- over 1 MB" if size > WARN_BYTES else ""
            print(f"ok       {video.name} -> {gif.name} ({human(size)}){warn}")
            done += 1
        else:
            print(f"FAILED   {video.name}")
            failed += 1

    total = sum(g.stat().st_size for g in GIF_DIR.glob("*.gif"))
    print(f"\nConverted: {done}, skipped: {skipped}, failed: {failed}. media/gif total: {human(total)}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
