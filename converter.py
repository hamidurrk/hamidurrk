import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SOURCE_DIR = ROOT / "media" / "source"
GIF_DIR = ROOT / "media" / "gif"
VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".webm"}


def convert(ffmpeg: str, src: Path, dst: Path, fps: int, width: int, duration: float) -> bool:
    filters = (
        f"fps={fps},scale={width}:-1:flags=lanczos,"
        "split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse"
    )
    cmd = [
        ffmpeg, "-y", "-loglevel", "error",
        "-t", str(duration), "-i", str(src), "-vf", filters, "-loop", "0", str(dst),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(result.stderr.strip(), file=sys.stderr)
        dst.unlink(missing_ok=True)
        return False
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fps", type=int, default=12, help="GIF frame rate (default 12)")
    parser.add_argument("--width", type=int, default=400, help="GIF width in px (default 400)")
    parser.add_argument("--duration", type=float, default=20, help="max seconds taken from the start of each video (default 20)")
    parser.add_argument("--force", action="store_true", help="overwrite existing GIFs")
    args = parser.parse_args()

    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        print("Error: ffmpeg not found on PATH.", file=sys.stderr)
        return 1

    GIF_DIR.mkdir(parents=True, exist_ok=True)
    videos = sorted(p for p in SOURCE_DIR.glob("*") if p.suffix.lower() in VIDEO_EXTS)
    if not videos:
        print(f"No videos found in {SOURCE_DIR}")
        return 0

    done = skipped = failed = 0
    for video in videos:
        gif = GIF_DIR / f"{video.stem}.gif"
        if gif.exists() and not args.force:
            print(f"skip     {video.name} (gif exists)")
            skipped += 1
        elif convert(ffmpeg, video, gif, args.fps, args.width, args.duration):
            print(f"ok       {video.name} -> {gif.name}")
            done += 1
        else:
            print(f"FAILED   {video.name}")
            failed += 1

    print(f"\nConverted: {done}, skipped: {skipped}, failed: {failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
