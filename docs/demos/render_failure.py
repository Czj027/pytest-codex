"""Render a synthetic trace's actual pytest failure as a small terminal animation.

Requires Pillow only for rendering. An optional argument selects the Python
interpreter with pytest and this project installed.
"""

import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def main():
    root = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        [
            sys.argv[1] if len(sys.argv) > 1 else sys.executable,
            "-m",
            "pytest",
            "docs/demos/test_conventions.py",
            "-q",
            "--tb=short",
            "--color=no",
        ],
        cwd=root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    assert result.returncode == 1 and "pip install requests" in result.stdout
    assert "1 failed" in result.stdout
    lines = ["$ python -m pytest docs/demos/test_conventions.py -q --tb=short", ""]
    lines.extend(result.stdout.strip().splitlines())
    fonts = ["C:/Windows/Fonts/consola.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"]
    font = next(
        (ImageFont.truetype(path, 20) for path in fonts if Path(path).exists()),
        ImageFont.load_default(),
    )
    frames = []
    for count in [1, 2, *range(3, len(lines) + 1, 2), len(lines)]:
        picture = Image.new("RGB", (1160, 112 + 28 * len(lines)), "#101820")
        draw = ImageDraw.Draw(picture)
        draw.text(
            (24, 20),
            "pytest-codex | synthetic trace, actual pytest failure | no model call",
            font=font,
            fill="#9fb1c2",
        )
        for index, line in enumerate(lines[:count]):
            color = "#ff7b72" if "failed" in line or line.startswith("E ") else "#d8e5ee"
            if "pip install requests" in line:
                color = "#ffd580"
            draw.text((24, 82 + index * 28), line[:91], font=font, fill=color)
        frames.append(picture)
    output = root / "docs/assets/failure.gif"
    frames[0].save(
        output,
        save_all=True,
        append_images=frames[1:],
        loop=0,
        duration=[500] * (len(frames) - 1) + [4000],
        optimize=True,
    )
    print(f"Rendered {len(frames)} frames: {output.name} ({output.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
