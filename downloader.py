import re
import sys
from pathlib import Path

from yt_dlp import YoutubeDL

ROOT = Path(__file__).resolve().parent
DATA_FILE = ROOT / "data" / "constant.ts"
SOURCE_DIR = ROOT / "media" / "source"

SLUG_RE = re.compile(r'slug:\s*"([^"]+)"')
EMBED_RE = re.compile(r"youtube\.com/embed/([A-Za-z0-9_-]{11})")


def parse_projects() -> list[tuple[str, str]]:
    text = DATA_FILE.read_text(encoding="utf-8")
    projects = []
    for block in text.split("\n  {")[1:]:
        slug, embed = SLUG_RE.search(block), EMBED_RE.search(block)
        if slug and embed:
            projects.append((slug.group(1), embed.group(1)))
    return projects


def main() -> int:
    SOURCE_DIR.mkdir(parents=True, exist_ok=True)
    failed = 0
    for slug, video_id in parse_projects():
        target = SOURCE_DIR / f"{slug}.mp4"
        if target.exists():
            print(f"skip     {slug} (exists)")
            continue
        opts = {
            "format": "bv*[height<=720][ext=mp4]/bv*[height<=720]/b[height<=720]",
            "outtmpl": str(SOURCE_DIR / f"{slug}.%(ext)s"),
            "merge_output_format": "mp4",
            "quiet": True,
            "no_warnings": True,
        }
        try:
            with YoutubeDL(opts) as ydl:
                ydl.download([f"https://youtu.be/{video_id}"])
            print(f"ok       {slug}")
        except Exception as exc:  # keep going on individual failures
            print(f"FAILED   {slug}: {exc}", file=sys.stderr)
            failed += 1
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
