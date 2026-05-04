"""Create clear Arabic Facebook images for job posts with Pillow."""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
import logging
from pathlib import Path
import re
from typing import Any
from urllib.parse import urlparse

import requests
from PIL import Image, ImageDraw, ImageFont

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
CANVAS_SIZE = 1080
REQUEST_TIMEOUT = 12


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


TITLE_BOX = Box(76, 250, 928, 330)
LOGO_BOX = Box(800, 78, 150, 150)
DETAIL_BOXES = [
    Box(704, 650, 300, 142),
    Box(390, 650, 300, 142),
    Box(76, 650, 300, 142),
]
FOOTER_BOX = Box(76, 840, 928, 112)


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Return a font with good Arabic support."""
    custom_fonts = (
        ["Cairo-Bold.ttf", "Tajawal-Bold.ttf", "NotoKufiArabic-Bold.ttf"]
        if bold
        else ["Cairo-Regular.ttf", "Tajawal-Regular.ttf", "NotoKufiArabic-Regular.ttf"]
    )
    candidates = [FONTS_DIR / name for name in custom_fonts]
    candidates.extend(
        [
            Path("C:/Windows/Fonts/arialbd.ttf") if bold else Path("C:/Windows/Fonts/arial.ttf"),
            Path("C:/Windows/Fonts/tahomabd.ttf") if bold else Path("C:/Windows/Fonts/tahoma.ttf"),
            Path("C:/Windows/Fonts/segoeuib.ttf") if bold else Path("C:/Windows/Fonts/segoeui.ttf"),
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")
            if bold
            else Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
            Path("/usr/share/fonts/truetype/noto/NotoNaskhArabic-Bold.ttf")
            if bold
            else Path("/usr/share/fonts/truetype/noto/NotoNaskhArabic-Regular.ttf"),
        ]
    )

    for path in candidates:
        try:
            if path.exists():
                return ImageFont.truetype(str(path), size=size)
        except OSError:
            continue

    LOGGER.warning("Could not find an Arabic-capable font; using Pillow default.")
    return ImageFont.load_default()


def _rtl(text: str) -> str:
    if arabic_reshaper is None or get_display is None:
        return text
    return get_display(arabic_reshaper.reshape(text))


def _text_size(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont) -> tuple[int, int]:
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0], bbox[3] - bbox[1]


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


def _logo_domains(job: dict[str, Any]) -> list[str]:
    domains: list[str] = []
    for key in ("company_domain", "domain", "website", "application_url", "announcement_url", "url"):
        domain = _domain_from_url(job.get(key))
        if domain and domain not in domains:
            domains.append(domain)
    return domains


def _download_image(url: str) -> Image.Image | None:
    try:
        response = requests.get(
            url,
            headers={"User-Agent": "MoroccoJobRadarBot/1.0"},
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        return Image.open(BytesIO(response.content)).convert("RGBA")
    except (requests.RequestException, OSError) as exc:
        LOGGER.debug("Logo fetch failed for %s: %s", url, exc)
        return None


def _load_logo(job: dict[str, Any]) -> Image.Image | None:
    logo_url = str(job.get("logo_url") or "").strip()
    if logo_url.startswith(("http://", "https://")):
        logo = _download_image(logo_url)
        if logo is not None:
            return logo

    for domain in _logo_domains(job):
        logo = _download_image(f"https://logo.clearbit.com/{domain}?size=256")
        if logo is not None:
            return logo
        logo = _download_image(f"https://www.google.com/s2/favicons?domain={domain}&sz=256")
        if logo is not None:
            return logo
    return None


def _fit_image(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    fitted = image.copy()
    fitted.thumbnail(size, Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", size, (255, 255, 255, 0))
    x = (size[0] - fitted.width) // 2
    y = (size[1] - fitted.height) // 2
    canvas.alpha_composite(fitted, (x, y))
    return canvas


def _wrap_pixels(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, max_width: int) -> list[str]:
    lines: list[str] = []
    for paragraph in str(text or "").splitlines() or [""]:
        words = paragraph.split()
        if not words:
            continue

        current = words[0]
        for word in words[1:]:
            candidate = f"{current} {word}"
            if _text_size(draw, _rtl(candidate), font)[0] <= max_width:
                current = candidate
            else:
                lines.append(current)
                current = word
        lines.append(current)
    return lines


def _draw_text_right(
    draw: ImageDraw.ImageDraw,
    text: str,
    box: Box,
    font: ImageFont.ImageFont,
    fill: str,
    *,
    line_spacing: int = 10,
    max_lines: int | None = None,
) -> int:
    lines = _wrap_pixels(draw, text, font, box.w)
    if max_lines is not None and len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = lines[-1].rstrip(" .،") + "..."

    y = box.y
    for line in lines:
        visual_line = _rtl(line)
        width, height = _text_size(draw, visual_line, font)
        if y + height > box.bottom:
            break
        draw.text((box.right - width, y), visual_line, font=font, fill=fill)
        y += height + line_spacing
    return y


def _fit_font_for_box(
    draw: ImageDraw.ImageDraw,
    text: str,
    box: Box,
    *,
    start: int,
    minimum: int,
    bold: bool = True,
    max_lines: int = 3,
) -> ImageFont.ImageFont:
    for size in range(start, minimum - 1, -3):
        font = _font(size, bold=bold)
        lines = _wrap_pixels(draw, text, font, box.w)
        if len(lines) > max_lines:
            continue
        line_heights = [_text_size(draw, _rtl(line), font)[1] for line in lines]
        total_height = sum(line_heights) + max(0, len(lines) - 1) * 14
        if total_height <= box.h:
            return font
    return _font(minimum, bold=bold)


def _company_initials(company: str) -> str:
    words = [word for word in re.split(r"\s+", company.strip()) if word]
    if not words:
        return "JOB"
    latin = [word[0].upper() for word in words if word[0].isascii() and word[0].isalnum()]
    if latin:
        return "".join(latin[:3])
    return "".join(word[0] for word in words[:2])


def _draw_gradient_background(image: Image.Image) -> None:
    draw = ImageDraw.Draw(image)
    top = (246, 248, 246)
    bottom = (231, 239, 234)
    for y in range(CANVAS_SIZE):
        ratio = y / (CANVAS_SIZE - 1)
        color = tuple(int(top[i] * (1 - ratio) + bottom[i] * ratio) for i in range(3))
        draw.line((0, y, CANVAS_SIZE, y), fill=color + (255,))

    draw.rectangle((0, 0, CANVAS_SIZE, 18), fill="#0b6b3a")
    draw.rectangle((0, CANVAS_SIZE - 18, CANVAS_SIZE, CANVAS_SIZE), fill="#c21f32")
    draw.rounded_rectangle((44, 48, 1036, 1018), radius=34, fill="#fffffff2", outline="#dde6df", width=3)


def _draw_badge(draw: ImageDraw.ImageDraw, text: str, xy: tuple[int, int], fill: str) -> None:
    font = _font(34, bold=True)
    visual = _rtl(text)
    width, height = _text_size(draw, visual, font)
    x, y = xy
    draw.rounded_rectangle((x - width - 32, y, x, y + height + 28), radius=18, fill=fill)
    draw.text((x - width - 16, y + 10), visual, font=font, fill="#ffffff")


def _draw_logo(image: Image.Image, draw: ImageDraw.ImageDraw, job: dict[str, Any]) -> None:
    company = _value_or_missing(job.get("company"))
    draw.rounded_rectangle(
        (LOGO_BOX.x - 12, LOGO_BOX.y - 12, LOGO_BOX.right + 12, LOGO_BOX.bottom + 12),
        radius=34,
        fill="#ffffff",
        outline="#d8e2dc",
        width=3,
    )
    logo = _load_logo(job)
    if logo is not None:
        image.alpha_composite(_fit_image(logo, (LOGO_BOX.w, LOGO_BOX.h)), (LOGO_BOX.x, LOGO_BOX.y))
        return

    initials = _rtl(_company_initials(company))
    font = _font(46, bold=True)
    width, height = _text_size(draw, initials, font)
    draw.rounded_rectangle((LOGO_BOX.x, LOGO_BOX.y, LOGO_BOX.right, LOGO_BOX.bottom), radius=28, fill="#edf7f1")
    draw.text(
        (LOGO_BOX.x + (LOGO_BOX.w - width) // 2, LOGO_BOX.y + (LOGO_BOX.h - height) // 2 - 2),
        initials,
        font=font,
        fill="#0b6b3a",
    )


def _draw_detail_card(draw: ImageDraw.ImageDraw, box: Box, label: str, value: Any) -> None:
    label_font = _font(28, bold=True)
    value_font = _font(33, bold=True)
    draw.rounded_rectangle((box.x, box.y, box.right, box.bottom), radius=22, fill="#f7faf8", outline="#dbe7df", width=2)
    _draw_text_right(draw, label, Box(box.x + 22, box.y + 18, box.w - 44, 36), label_font, "#0b6b3a", max_lines=1)
    _draw_text_right(
        draw,
        _value_or_missing(value),
        Box(box.x + 22, box.y + 62, box.w - 44, 58),
        value_font,
        "#18212a",
        line_spacing=4,
        max_lines=2,
    )


def _draw_footer(draw: ImageDraw.ImageDraw) -> None:
    cta_font = _font(42, bold=True)
    hint_font = _font(28, bold=True)
    draw.rounded_rectangle(
        (FOOTER_BOX.x, FOOTER_BOX.y, FOOTER_BOX.right, FOOTER_BOX.bottom),
        radius=24,
        fill="#0b6b3a",
    )
    _draw_text_right(
        draw,
        "رابط التقديم الرسمي في أول تعليق",
        Box(FOOTER_BOX.x + 34, FOOTER_BOX.y + 18, FOOTER_BOX.w - 68, 54),
        cta_font,
        "#ffffff",
        max_lines=1,
    )
    _draw_text_right(
        draw,
        "تابع الصفحة لتصلك آخر مباريات وفرص العمل في المغرب",
        Box(FOOTER_BOX.x + 34, FOOTER_BOX.y + 72, FOOTER_BOX.w - 68, 36),
        hint_font,
        "#dff4e7",
        max_lines=1,
    )


def create_job_image(job: dict[str, Any], post_data: dict[str, Any]) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGBA", (CANVAS_SIZE, CANVAS_SIZE), "#f6f8f6")
    _draw_gradient_background(image)
    draw = ImageDraw.Draw(image)

    _draw_badge(
        draw,
        "مباراة توظيف" if _is_government_job(job) else "فرصة عمل",
        (720, 86),
        "#c21f32" if _is_government_job(job) else "#0b6b3a",
    )
    _draw_badge(draw, "وظائف المغرب", (720, 154), "#17212b")
    _draw_logo(image, draw, job)

    title = str(post_data.get("image_title") or job.get("title") or "فرصة عمل جديدة").strip()
    title_font = _fit_font_for_box(draw, title, TITLE_BOX, start=88, minimum=56, max_lines=3)
    _draw_text_right(draw, title, TITLE_BOX, title_font, "#121820", line_spacing=14, max_lines=3)

    company = _value_or_missing(job.get("company"))
    location = _value_or_missing(job.get("location"))
    final_label = "آخر أجل" if _is_government_job(job) else "نمط العمل"
    final_value = job.get("deadline") if _is_government_job(job) else ("عن بعد" if job.get("remote") else "حسب الإعلان")

    _draw_detail_card(draw, DETAIL_BOXES[0], "الشركة / المؤسسة", company)
    _draw_detail_card(draw, DETAIL_BOXES[1], "المدينة", location)
    _draw_detail_card(draw, DETAIL_BOXES[2], final_label, final_value)
    _draw_footer(draw)

    file_name = f"{job.get('source', 'job')}-{_safe_filename(str(job.get('job_id') or job.get('title')))}.png"
    output_path = OUTPUT_DIR / file_name
    image.convert("RGB").save(output_path, "PNG", optimize=True)
    LOGGER.info("Generated image: %s", output_path)
    return output_path
