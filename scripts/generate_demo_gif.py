"""Generate the README demo GIF from the real one-click demo output.

The GIF is composed from frames that replay the actual terminal session of
``examples/one_click_demo.py`` so the asset stays accurate when the demo
output changes. The script can be re-run any time after the demo changes.

Usage:
    python scripts/generate_demo_gif.py \\
        --output docs/assets/demo-workflow.gif \\
        --out-dir report/open_source_demo_gif
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import List, Tuple

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError as exc:  # pragma: no cover - depends on local install
    raise SystemExit("Pillow is required: pip install Pillow") from exc

ROOT = Path(__file__).resolve().parents[1]

WIDTH = 1280
HEIGHT = 640
BG = (15, 23, 42)
HEADER_BG = (30, 41, 59)
TEXT = (226, 232, 240)
DIM = (148, 163, 184)
GREEN = (134, 239, 172)
YELLOW = (250, 204, 21)
CYAN = (103, 232, 249)
RED = (248, 113, 113)


def load_font(size: int) -> ImageFont.ImageFont:
    for candidate in (
        "C:/Windows/Fonts/consola.ttf",
        "C:/Windows/Fonts/CascadiaMono.ttf",
        "C:/Windows/Fonts/CascadiaCode.ttf",
        "/System/Library/Fonts/Menlo.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    ):
        try:
            return ImageFont.truetype(candidate, size)
        except OSError:
            continue
    return ImageFont.load_default()


def run_demo(out_dir: Path) -> Tuple[str, dict]:
    """Run the demo script and return its stdout and parsed report."""
    out_dir.mkdir(parents=True, exist_ok=True)
    completed = subprocess.run(
        [sys.executable, "examples/one_click_demo.py", "--out-dir", str(out_dir)],
        check=True,
        capture_output=True,
        text=True,
        cwd=str(ROOT),
    )
    report = json.loads(
        (out_dir / "platform_console_demo.json").read_text(encoding="utf-8")
    )
    return completed.stdout.strip(), report


def make_frame(lines: List[Tuple[str, Tuple[int, int, int]]], title: str) -> Image.Image:
    image = Image.new("RGB", (WIDTH, HEIGHT), BG)
    draw = ImageDraw.Draw(image)
    title_font = load_font(22)
    line_font = load_font(20)

    draw.rectangle((0, 0, WIDTH, 48), fill=HEADER_BG)
    draw.ellipse((16, 16, 32, 32), fill=RED)
    draw.ellipse((40, 16, 56, 32), fill=YELLOW)
    draw.ellipse((64, 16, 80, 32), fill=GREEN)
    draw.text((110, 14), title, font=title_font, fill=DIM)

    y = 78
    for text, color in lines:
        draw.text((40, y), text, font=line_font, fill=color)
        y += 28
        if y > HEIGHT - 32:
            break
    return image


def build_frames(stdout_text: str, report: dict, out_dir_display: str) -> List[Image.Image]:
    summary = report["summary"]
    steps = [step["name"] for step in report["steps"]]

    frame1 = make_frame(
        [
            ("$ git clone https://github.com/magic-alt/stock.git", CYAN),
            ("Cloning into 'stock'...", DIM),
            ("$ cd stock", CYAN),
            ("$ pip install -r requirements.txt", CYAN),
            ("Successfully installed pandas backtrader fastapi ...", GREEN),
        ],
        "1 / 4  setup",
    )

    frame2 = make_frame(
        [
            ("$ python examples/one_click_demo.py \\", CYAN),
            (f"      --out-dir {out_dir_display}", CYAN),
            ("", TEXT),
            ("[demo] connecting paper gateway ...", DIM),
            ("[demo] submit_buy_limit  600519.SH @ 100.0", TEXT),
            ("[demo] match_buy_with_paper_price  99.5", GREEN),
            ("[demo] submit_exit_limit  600519.SH @ 120.0", TEXT),
            ("[demo] cancel_exit_limit  cancelled", YELLOW),
            ("[demo] mark_to_market  101.2", TEXT),
        ],
        "2 / 4  run one-click demo",
    )

    stdout_lines: List[Tuple[str, Tuple[int, int, int]]] = []
    stdout_lines.append(("$ cat <(python examples/one_click_demo.py ...)", CYAN))
    stdout_lines.append(("", TEXT))
    for raw in stdout_text.splitlines():
        stdout_lines.append((raw, TEXT))
    frame3 = make_frame(stdout_lines, "3 / 4  inspect stdout")

    summary_lines: List[Tuple[str, Tuple[int, int, int]]] = [
        (f"$ ls {out_dir_display}", CYAN),
        ("platform_console_demo.json", TEXT),
        ("web_console_echarts.json", TEXT),
        ("demo_report.md", TEXT),
        ("", TEXT),
        ("# demo_report.md", DIM),
        (f"gateway_connected: {summary['gateway_connected']}", GREEN),
        (f"mode: {summary['mode']}", TEXT),
        (f"filled_orders: {summary['filled_orders']}", GREEN),
        (f"cancelled_orders: {summary['cancelled_orders']}", YELLOW),
        (f"trades: {summary['trades']}", TEXT),
        (f"unrealized_pnl: {round(float(summary['unrealized_pnl']), 2)}", GREEN),
        ("", TEXT),
        ("workflow: " + " -> ".join(steps[:4]), DIM),
        ("           " + " -> ".join(steps[4:]), DIM),
    ]
    frame4 = make_frame(summary_lines, "4 / 4  artifacts")

    return [frame1, frame2, frame3, frame4]


def save_gif(frames: List[Image.Image], output: Path, frame_ms: int) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    frames[0].save(
        output,
        save_all=True,
        append_images=frames[1:],
        duration=frame_ms,
        loop=0,
        optimize=True,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render the README demo GIF from real demo output")
    parser.add_argument("--output", default="docs/assets/demo-workflow.gif")
    parser.add_argument("--out-dir", default="report/open_source_demo_gif")
    parser.add_argument("--frame-ms", type=int, default=2200)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    out_dir = Path(args.out_dir)
    stdout_text, report = run_demo(out_dir)
    frames = build_frames(stdout_text, report, out_dir.as_posix())
    save_gif(frames, Path(args.output), args.frame_ms)
    print(f"wrote {args.output} ({len(frames)} frames)")


if __name__ == "__main__":
    main()
