"""Normalize browser captures and assemble the design-review contact sheets.

This script packages existing screenshots. It does not render or implement UI.
Run from any directory with Python and Pillow installed.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "design" / "mockups"
SCREENS = [
    ("01", "autocomplete", "Refine / Autocomplete"),
    ("02", "choice", "Refine / Multiple choice"),
    ("03", "diff", "Refine / Confirm diff"),
    ("04", "none", "Refine / No suggestion"),
    ("05", "error", "Refine / Service error"),
    ("06", "knowledge", "Knowledge / Library"),
    ("07", "detail", "Knowledge / Source"),
    ("08", "add", "Knowledge / Add source"),
    ("09", "api", "Activity / API calls"),
    ("10", "ai", "Activity / AI calls"),
    ("11", "event", "Activity / Request detail"),
    ("12", "settings", "Settings"),
    ("13", "empty", "Refine / Empty draft"),
    ("14", "empty-library", "Knowledge / Empty library"),
    ("15", "import-error", "Knowledge / Ingestion error"),
]
DARK = {"autocomplete", "knowledge", "api", "settings"}


def font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in [
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def paste_thumbnail(sheet: Image.Image, path: Path, box: tuple[int, int, int, int]) -> None:
    image = Image.open(path).convert("RGB")
    image.thumbnail((box[2], box[3]), Image.Resampling.LANCZOS)
    sheet.paste(image, (box[0], box[1]))
    ImageDraw.Draw(sheet).rectangle(
        (box[0], box[1], box[0] + image.width, box[1] + image.height), outline="#cbd4c8"
    )


def contact_sheet(groups: list[tuple[str, str, str, str]], filename: str, columns: int) -> None:
    cell_width, cell_height, gap, margin = 420, 404, 20, 30
    rows = (len(groups) + columns - 1) // columns
    width = margin * 2 + columns * cell_width + (columns - 1) * gap
    height = 130 + rows * cell_height + (rows - 1) * gap + 46
    sheet = Image.new("RGB", (width, height), "#f5f5ef")
    draw = ImageDraw.Draw(sheet)
    draw.text((margin, 24), "Prompt Enhance", font=font(34), fill="#202b25")
    draw.text((margin, 76), "DESIGN REVIEW V1  /  DESKTOP + MOBILE  /  FIXTURE DATA", font=font(14), fill="#5e6c62")
    for index, (id_, state, title, theme) in enumerate(groups):
        x = margin + (index % columns) * (cell_width + gap)
        y = 130 + (index // columns) * (cell_height + gap)
        draw.rounded_rectangle((x, y, x + cell_width, y + cell_height), 8, fill="#ffffff", outline="#d5dbd2")
        draw.text((x + 14, y + 14), f"{id_}  {title}", font=font(15), fill="#202b25")
        draw.text((x + 14, y + 40), theme.upper(), font=font(10), fill="#5e6c62")
        if theme == "panel":
            paste_thumbnail(sheet, OUTPUT / "01-autocomplete-panel-light.png", (x + 14, y + 68, 390, 322))
        else:
            paste_thumbnail(sheet, OUTPUT / f"{id_}-{state}-desktop-{theme}.png", (x + 14, y + 68, 292, 322))
            paste_thumbnail(sheet, OUTPUT / f"{id_}-{state}-mobile-{theme}.png", (x + 320, y + 68, 82, 322))
    draw.text((margin, height - 28), "Approval pending. Full-size images and interactive design artifacts are available in the gallery.", font=font(12), fill="#5e6c62")
    sheet.save(OUTPUT / filename)


def main() -> None:
    entries = []
    for id_, state, title in SCREENS:
        themes = ["light", "dark"] if state in DARK else ["light"]
        for theme in themes:
            for device, viewport in [("desktop", (1280, 900)), ("mobile", (390, 1000))]:
                entries.append((id_, state, title, theme, device, viewport))
    entries.append(("01", "autocomplete", "Refine / Narrow companion panel", "light", "panel", (560, 1000)))
    manifest = []
    for id_, state, title, theme, device, viewport in entries:
        filename = f"{id_}-{state}-{device}-{theme}.png"
        path = OUTPUT / filename
        with Image.open(path) as source:
            image = source.convert("RGB")
        if image.width != viewport[0]:
            raise ValueError(f"Wrong capture width: {filename}: {image.size}")
        image.save(path, format="PNG")
        manifest.append({
            "id": id_, "screen": state, "title": title, "theme": theme, "device": device,
            "file": filename, "viewport": {"width": viewport[0], "height": viewport[1]},
            "image": {"width": image.width, "height": image.height},
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        })
    (OUTPUT / "manifest.json").write_text(json.dumps({
        "version": 1, "status": "awaiting_user_approval", "captured_at": "2026-10-24",
        "capture": "Codex in-app browser via cua_repl; full-page screenshots",
        "count": len(manifest), "screens": manifest,
    }, indent=2) + "\n")
    groups = [(id_, state, title, "light") for id_, state, title in SCREENS]
    groups += [(id_, state, title, "dark") for id_, state, title in SCREENS if state in DARK]
    groups.append(("01", "autocomplete", "Narrow companion panel", "panel"))
    contact_sheet(groups, "contact-sheet.png", 4)
    contact_sheet([g for g in groups if g[1] in DARK and g[3] == "light"], "overview.png", 2)
    print(f"Packaged {len(manifest)} screenshots, complete contact sheet, and four-tab overview.")


if __name__ == "__main__":
    main()
