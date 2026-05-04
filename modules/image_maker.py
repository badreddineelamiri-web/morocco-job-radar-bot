"""Create Arabic Facebook job images with clear RTL typography."""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
import logging
from pathlib import Path
import re
from typing import Any
from urllib.parse import urlparse

import requests
from PIL import Image, ImageDraw, ImageFont, features

try:
    import arabic_reshaper
    from bidi.algorithm import get_display
except ImportError:  # pragma: no cover - optional dependency fallback.
    arabic_reshaper = None
    get_display = None


LOGGER = logging.getLogger(__name__)
ASSETS_DIR = Path("assets")
FONTS_DIR = ASSETS_DIR / "fonts"
OUTPUT_DIR = Path("data/generated_images")
TEMPLATE_PATH = ASSETS_DIR / "job_template.png"
CANVAS_SIZE = 1080
REQUEST_TIMEOUT = 12
HAS_RAQM = bool(features.check("raqm"))


@dataclass(frozen=True)
class Box:
    x: int
    y: int
    w: int
    h: int

    @property
    def right(self) -> int:
        return self.x + self.w

    @property
    def bottom(self) -> int:
        return self.y + self.h


TITLE_BOX = Box(82, 220, 916, 340)
DETAIL_BOXES = [
    Box(82, 650, 290, 150),
    Box(395, 650, 290, 150),
    Box(708, 650, 290, 150),
]
FOOTER_BOX = Box(82, 850, 916, 105)


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Return a font with Arabic glyph coverage."""
    custom_fonts = (
        ["Cairo-Bold.ttf", "Tajawal-Bold.ttf", "NotoKufiArabic-Bold.ttf", "NotoNaskhArabic-Bold.ttf"]
        if bold
        else ["Cairo-Regular.ttf", "Tajawal-Regular.ttf", "NotoKufiArabic-Regular.ttf", "NotoNaskhArabic-Regular.ttf"]
    )
    candidates = [FONTS_DIR / name for name in custom_fonts]
    candidates.extend(
        [
            Path("C:/Windows/Fonts/tahomabd.ttf") if bold else Path("C:/Windows/Fonts/tahoma.ttf"),
            Path("C:/Windows/Fonts/arialbd.ttf") if bold else Path("C:/Windows/Fonts/arial.ttf"),
            Path("C:/Windows/Fonts/segoeuib.ttf") if bold else Path("C:/Windows/Fonts/segoeui.ttf"),
            Path("/usr/share/fonts/truetype/noto/NotoNaskhArabic-Bold.ttf")
            if bold
            else Path("/usr/share/fonts/truetype/noto/NotoNaskhArabic-Regular.ttf"),
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")
            if bold
            else Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        ]
    )

    layout_engine = ImageFont.Layout.RAQM if HAS_RAQM else ImageFont.Layout.BASIC
    for path in candidates:
        try:
            if path.exists():
                return ImageFont.truetype(str(path), size=size, layout_engine=layout_engine)
        except OSError:
            continue

    LOGGER.warning("Could not find an Arabic-capable font; using Pillow default.")
    return ImageFont.load_default()


def _visual_text(text: str) -> str:
    """Return text prepared for drawing when RAQM is not available."""
    if HAS_RAQM:
        return text
    if arabic_reshaper is None or get_display is None:
        return text
    return get_display(arabic_reshaper.reshape(text))


def _text_bbox(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.ImageFont,
    *,
    anchor: str | None = None,
) -> tuple[int, int, int, int]:
    kwargs = {"font": font}
    if HAS_RAQM:
        kwargs.update({"direction": "rtl", "language": "ar"})
    if anchor:
        kwargs["anchor"] = anchor
    return draw.textbbox((0, 0), _visual_text(text), **kwargs)


def _text_size(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont) -> tuple[int, int]:
    bbox = _text_bbox(draw, text, font)
    return bbox[2] - bbox[0], bbox[3] - bbox[1]


def _draw_rtl(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    text: str,
    font: ImageFont.ImageFont,
    fill: str,
    *,
    anchor: str = "ra",
) -> None:
    visual = _visual_text(text)
    kwargs: dict[str, Any] = {"font": font, "fill": fill}
    if HAS_RAQM:
        kwargs.update({"direction": "rtl", "language": "ar", "anchor": anchor})
        draw.text(xy, visual, **kwargs)
        return

    width, _ = _text_size(draw, text, font)
    x = xy[0] - width if anchor.endswith("a") else xy[0]
    draw.text((x, xy[1]), visual, **kwargs)


def _value_or_missing(value: Any) -> str:
    text = str(value).strip() if value else ""
    return text or "غير مذكور"


def _safe_filename(value: str) -> str:
    safe = "".join(char for char in value if char.isalnum() or char in ("-", "_")).strip()
    return safe[:80] or "job"


def _is_government_job(job: dict[str, Any]) -> bool:
    return job.get("job_type") == "government"


def _domain_from_url(value: Any) -> str:
    url = str(value or "").strip()
    if not url:
        return ""
    parsed = urlparse(url if "://" in url else f"https://{url}")
    host = parsed.netloc.lower().replace("www.", "")
    return host.split(":")[0]


def _download_image(url: str) -> Image.Image | None:
    try:
        response = requests.get(url, headers={"User-Agent": "MoroccoJobRadarBot/1.0"}, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        return Image.open(BytesIO(response.content)).convert("RGBA")
    except (requests.RequestException, OSError) as exc:
        LOGGER.debug("Logo fetch failed for %s: %s", url, exc)
        return None


def _wrap_pixels(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, max_width: int) -> list[str]:
    lines: list[str] = []
    for paragraph in str(text or "").splitlines() or [""]:
        words = paragraph.split()
        if not words:
            continue
        current = words[0]
        for word in words[1:]:
            candidate = f"{current} {word}"
            if _text_size(draw, candidate, font)[0] <= max_width:
                current = candidate
            else:
                lines.append(current)
                current = word
        lines.append(current)
    return lines


def _draw_wrapped_center(
    draw: ImageDraw.ImageDraw,
    text: str,
    box: Box,
    font: ImageFont.ImageFont,
    fill: str,
    *,
    line_spacing: int = 12,
    max_lines: int | None = None,
) -> int:
    lines = _wrap_pixels(draw, text, font, box.w)
    if max_lines is not None and len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = lines[-1].rstrip(" .،") + "..."

    heights = [_text_size(draw, line, font)[1] for line in lines]
    total_height = sum(heights) + max(0, len(lines) - 1) * line_spacing
    y = box.y + max(0, (box.h - total_height) // 2)
    center_x = box.x + box.w // 2
    for line, height in zip(lines, heights):
        visual = _visual_text(line)
        kwargs: dict[str, Any] = {"font": font, "fill": fill, "anchor": "ma"}
        if HAS_RAQM:
            kwargs.update({"direction": "rtl", "language": "ar"})
        draw.text((center_x, y), visual, **kwargs)
        y += height + line_spacing
    return y


def _draw_wrapped_right(
    draw: ImageDraw.ImageDraw,
    text: str,
    box: Box,
    font: ImageFont.ImageFont,
    fill: str,
    *,
    line_spacing: int = 8,
    max_lines: int | None = None,
) -> int:
    lines = _wrap_pixels(draw, text, font, box.w)
    if max_lines is not None and len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = lines[-1].rstrip(" .،") + "..."

    y = box.y
    for line in lines:
        _, height = _text_size(draw, line, font)
        if y + height > box.bottom:
            break
        _draw_rtl(draw, (box.right, y), line, font, fill)
        y += height + line_spacing
    return y


def _fit_font_for_box(
    draw: ImageDraw.ImageDraw,
    text: str,
    box: Box,
    *,
    start: int,
    minimum: int,
    max_lines: int,
) -> ImageFont.ImageFont:
    for size in range(start, minimum - 1, -3):
        font = _font(size, bold=True)
        lines = _wrap_pixels(draw, text, font, box.w)
        if len(lines) > max_lines:
            continue
        heights = [_text_size(draw, line, font)[1] for line in lines]
        total_height = sum(heights) + max(0, len(lines) - 1) * 12
        if total_height <= box.h:
            return font
    return _font(minimum, bold=True)


def _base_canvas() -> tuple[Image.Image, ImageDraw.ImageDraw]:
    if TEMPLATE_PATH.exists():
        image = Image.open(TEMPLATE_PATH).convert("RGBA")
        if image.size != (CANVAS_SIZE, CANVAS_SIZE):
            image = image.resize((CANVAS_SIZE, CANVAS_SIZE), Image.Resampling.LANCZOS)
    else:
        image = Image.new("RGBA", (CANVAS_SIZE, CANVAS_SIZE), "#f7f8fb")
        draw = ImageDraw.Draw(image)
        draw.rounded_rectangle((50, 70, 1030, 1010), radius=36, fill="#ffffff")
    return image, ImageDraw.Draw(image)


def _detail_items(job: dict[str, Any]) -> list[tuple[str, str]]:
    final_label = "آخر أجل" if _is_government_job(job) else "نمط العمل"
    final_value = job.get("deadline") if _is_government_job(job) else ("عن بعد" if job.get("remote") else "حسب الإعلان")
    return [
        ("المؤسسة", _value_or_missing(job.get("company"))),
        ("المدينة", _value_or_missing(job.get("location"))),
        (final_label, _value_or_missing(final_value)),
    ]


def _draw_detail_box(draw: ImageDraw.ImageDraw, box: Box, label: str, value: str) -> None:
    label_font = _font(30, bold=True)
    value_font = _font(33, bold=True)
    draw.rounded_rectangle((box.x, box.y, box.right, box.bottom), radius=20, fill="#fffffff4", outline="#e2e2df", width=2)
    _draw_wrapped_right(draw, label, Box(box.x + 20, box.y + 20, box.w - 40, 38), label_font, "#08743f", max_lines=1)
    _draw_wrapped_right(draw, value, Box(box.x + 20, box.y + 66, box.w - 40, 72), value_font, "#151b24", max_lines=2)


def _draw_footer(draw: ImageDraw.ImageDraw) -> None:
    cta_font = _font(44, bold=True)
    hint_font = _font(28, bold=True)
    draw.rounded_rectangle((FOOTER_BOX.x, FOOTER_BOX.y, FOOTER_BOX.right, FOOTER_BOX.bottom), radius=20, fill="#08743f")
    _draw_wrapped_center(
        draw,
        "رابط التقديم الرسمي في أول تعليق",
        Box(FOOTER_BOX.x + 30, FOOTER_BOX.y + 14, FOOTER_BOX.w - 60, 50),
        cta_font,
        "#ffffff",
        max_lines=1,
    )
    _draw_wrapped_center(
        draw,
        "تابع الصفحة لتصلك آخر مباريات وفرص العمل في المغرب",
        Box(FOOTER_BOX.x + 30, FOOTER_BOX.y + 66, FOOTER_BOX.w - 60, 30),
        hint_font,
        "#e8fff0",
        max_lines=1,
    )


def create_job_image(job: dict[str, Any], post_data: dict[str, Any]) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    image, draw = _base_canvas()

    title = str(post_data.get("image_title") or job.get("title") or "فرصة عمل جديدة").strip()
    title_font = _fit_font_for_box(draw, title, TITLE_BOX, start=86, minimum=50, max_lines=3)
    _draw_wrapped_center(draw, title, TITLE_BOX, title_font, "#111820", line_spacing=14, max_lines=3)

    for box, (label, value) in zip(DETAIL_BOXES, _detail_items(job)):
        _draw_detail_box(draw, box, label, value)
    _draw_footer(draw)

    file_name = f"{job.get('source', 'job')}-{_safe_filename(str(job.get('job_id') or job.get('title')))}.png"
    output_path = OUTPUT_DIR / file_name
    image.convert("RGB").save(output_path, "PNG", optimize=True)
    LOGGER.info("Generated image: %s", output_path)
    return output_path
