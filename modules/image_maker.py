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
TEMPLATE_PATHS = (
    ASSETS_DIR / "job_template.png",
    ASSETS_DIR / "fonts" / "assets" / "job_template.png",
)
CANVAS_SIZE = 1080
REQUEST_TIMEOUT = 12
HAS_RAQM = bool(features.check("raqm"))
SOURCE_TRANSLATIONS = {
    "Ministere Industrie Commerce": "وزارة الصناعة والتجارة",
    "Ministere Equipement Eau": "وزارة التجهيز والماء",
    "Ministere Transport Logistique": "وزارة النقل واللوجستيك",
    "Ministere Habitat Urbanisme": "وزارة إعداد التراب الوطني والتعمير والإسكان",
    "Emploi Public": "بوابة التشغيل العمومي",
    "ANAPEC": "أنابيك",
    "OFPPT": "مكتب التكوين المهني وإنعاش الشغل",
    "Enseignement Superieur Recrutement": "وزارة التعليم العالي والبحث العلمي",
    "Collectivites Territoriales": "الجماعات الترابية",
}
CITY_TRANSLATIONS = {
    "rabat": "الرباط",
    "casablanca": "الدار البيضاء",
    "casa-nouacer": "الدار البيضاء - النواصر",
    "marrakech": "مراكش",
    "tanger": "طنجة",
    "fes": "فاس",
    "fès": "فاس",
    "agadir": "أكادير",
    "sale": "سلا",
    "salé": "سلا",
    "kenitra": "القنيطرة",
    "oujda": "وجدة",
    "meknes": "مكناس",
    "el jadida": "الجديدة",
}


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


CONTENT_BOX = Box(86, 142, 908, 720)
TITLE_BOX = Box(126, 220, 828, 108)
ORGANIZER_BOX = Box(126, 350, 828, 78)
HIGHLIGHT_BOXES = [
    Box(126, 456, 252, 104),
    Box(414, 456, 252, 104),
    Box(702, 456, 252, 104),
]
INFO_GRID_BOXES = [
    Box(126, 596, 396, 76),
    Box(558, 596, 396, 76),
    Box(126, 690, 396, 76),
    Box(558, 690, 396, 76),
    Box(126, 784, 396, 76),
    Box(558, 784, 396, 76),
]


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
            Path("/usr/share/fonts/truetype/noto/NotoSansArabic-Bold.ttf")
            if bold
            else Path("/usr/share/fonts/truetype/noto/NotoSansArabic-Regular.ttf"),
            Path("/usr/share/fonts/truetype/noto/NotoKufiArabic-Bold.ttf")
            if bold
            else Path("/usr/share/fonts/truetype/noto/NotoKufiArabic-Regular.ttf"),
            Path("/usr/share/fonts/opentype/noto/NotoNaskhArabic-Bold.ttf")
            if bold
            else Path("/usr/share/fonts/opentype/noto/NotoNaskhArabic-Regular.ttf"),
            Path("/usr/share/fonts/opentype/noto/NotoSansArabic-Bold.ttf")
            if bold
            else Path("/usr/share/fonts/opentype/noto/NotoSansArabic-Regular.ttf"),
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
    return text or "غير محدد"


def _first_value(job: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = job.get(key)
        if value:
            return str(value).strip()
    return ""


def _display_organization(job: dict[str, Any]) -> str:
    value = _first_value(job, "organization", "company", "source_name", "source")
    return SOURCE_TRANSLATIONS.get(value, value)


def _clean_location(value: Any) -> str:
    text = str(value or "").strip()
    lowered = text.lower()
    if not text or lowered in {"morocco", "maroc", "المغرب"}:
        return "على الصعيد الوطني"
    if lowered in CITY_TRANSLATIONS:
        return CITY_TRANSLATIONS[lowered]
    return text


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


def _draw_soft_shadow(draw: ImageDraw.ImageDraw, box: Box, radius: int = 22) -> None:
    for offset, color in ((8, "#d9dee866"), (4, "#edf0f655")):
        draw.rounded_rectangle(
            (box.x + offset, box.y + offset, box.right + offset, box.bottom + offset),
            radius=radius,
            fill=color,
        )


def _draw_moroccan_frame(draw: ImageDraw.ImageDraw) -> None:
    draw.rectangle((0, 0, CANVAS_SIZE, CANVAS_SIZE), fill="#071422")
    draw.rectangle((0, 972, 540, CANVAS_SIZE), fill="#b71822")
    draw.rectangle((540, 972, CANVAS_SIZE, CANVAS_SIZE), fill="#08743f")
    draw.polygon([(0, 972), (0, 1080), (420, 1080), (250, 1020)], fill="#cf1f28")
    draw.polygon([(1080, 972), (1080, 1080), (660, 1080), (830, 1020)], fill="#0a8950")
    draw.arc((-120, 850, 540, 1240), 188, 334, fill="#e6b25c", width=7)
    draw.arc((540, 850, 1200, 1240), 206, 352, fill="#e6b25c", width=7)
    for x in (18, 1040):
        draw.line((x, 22, x, 160), fill="#b9863f", width=2)
        draw.line((x, 22, x + (-120 if x > 500 else 120), 22), fill="#b9863f", width=2)
    for x, y in ((64, 52), (1016, 52), (540, 1028)):
        draw.regular_polygon((x, y, 18), n_sides=5, rotation=-18, outline="#08743f", width=2)


def _base_canvas() -> tuple[Image.Image, ImageDraw.ImageDraw]:
    image = None
    for template_path in TEMPLATE_PATHS:
        if template_path.exists():
            image = Image.open(template_path).convert("RGBA")
            if image.size != (CANVAS_SIZE, CANVAS_SIZE):
                image = image.resize((CANVAS_SIZE, CANVAS_SIZE), Image.Resampling.LANCZOS)
            break
    if image is None:
        image = Image.new("RGBA", (CANVAS_SIZE, CANVAS_SIZE), "#071422")
        draw = ImageDraw.Draw(image)
        _draw_moroccan_frame(draw)
        draw.rounded_rectangle((54, 118, 1026, 1000), radius=42, fill="#ffffff", outline="#e6b25c", width=3)
    return image, ImageDraw.Draw(image)


def _detail_items(job: dict[str, Any]) -> list[tuple[str, str]]:
    employment_type = _first_value(job, "employment_type", "recruitment_type") or (
        "توظيف نظامي" if _is_government_job(job) else ""
    )
    deposit_type = _first_value(job, "deposit_type", "submission_type")
    if not deposit_type and _first_value(job, "application_url", "announcement_url", "url"):
        deposit_type = "حسب الإعلان الرسمي"

    candidates = [
        ("نوع الإعلان", _announcement_label(job)),
        ("التخصص", _first_value(job, "specialty", "speciality", "field")),
        ("الدرجة", _first_value(job, "grade", "degree")),
        ("نوع التوظيف", employment_type),
        ("نوع الإيداع", deposit_type),
        ("مكان العمل", _clean_location(job.get("location"))),
        ("تاريخ النشر", _first_value(job, "published_at", "publication_date", "publish_date")),
        ("المرجع", _first_value(job, "reference")),
    ]
    return [(label, value) for label, value in candidates if value][:6]


def _highlight_items(job: dict[str, Any]) -> list[tuple[str, str]]:
    return [
        ("عدد المناصب", _value_or_missing(job.get("positions"))),
        ("آخر أجل", _value_or_missing(job.get("deadline"))),
        ("تاريخ المباراة", _value_or_missing(job.get("exam_date"))),
    ]


def _category_label(job: dict[str, Any], post_data: dict[str, Any]) -> str:
    main_category = str(job.get("main_category_label") or "").strip()
    if main_category:
        return main_category
    explicit_job = str(job.get("announcement_type_label") or "").strip()
    if explicit_job:
        return explicit_job
    explicit = str(post_data.get("category") or "").strip()
    if explicit:
        return explicit
    if job.get("job_type") == "scholarship":
        return "منحة أو تكوين"
    if _is_government_job(job):
        return "مباراة توظيف"
    return "فرصة عمل"


def _announcement_label(job: dict[str, Any]) -> str:
    label = str(job.get("announcement_type_label") or "").strip()
    return label or "إعلان موثق"


def _draw_detail_box(draw: ImageDraw.ImageDraw, box: Box, label: str, value: str) -> None:
    label_font = _font(23, bold=True)
    value_font = _fit_font_for_box(draw, value, Box(box.x + 22, box.y + 36, box.w - 44, 36), start=25, minimum=18, max_lines=2)
    _draw_soft_shadow(draw, box, radius=15)
    draw.rounded_rectangle((box.x, box.y, box.right, box.bottom), radius=15, fill="#ffffff", outline="#e7e2d8", width=2)
    draw.rounded_rectangle((box.right - 10, box.y + 14, box.right - 4, box.bottom - 14), radius=3, fill="#08743f")
    _draw_wrapped_right(draw, label, Box(box.x + 22, box.y + 10, box.w - 44, 24), label_font, "#08743f", max_lines=1)
    _draw_wrapped_right(draw, value, Box(box.x + 22, box.y + 39, box.w - 44, 35), value_font, "#121923", max_lines=2)


def _draw_highlight_box(draw: ImageDraw.ImageDraw, box: Box, label: str, value: str) -> None:
    label_font = _font(25, bold=True)
    value_font = _fit_font_for_box(draw, value, Box(box.x + 18, box.y + 48, box.w - 36, 52), start=34, minimum=24, max_lines=2)
    _draw_soft_shadow(draw, box, radius=20)
    draw.rounded_rectangle((box.x, box.y, box.right, box.bottom), radius=20, fill="#f9fbfd", outline="#e1e6ec", width=2)
    _draw_wrapped_center(draw, label, Box(box.x + 18, box.y + 14, box.w - 36, 28), label_font, "#6b7280", max_lines=1)
    _draw_wrapped_center(draw, value, Box(box.x + 18, box.y + 50, box.w - 36, 54), value_font, "#111820", max_lines=2)


def create_job_image(job: dict[str, Any], post_data: dict[str, Any]) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    image, draw = _base_canvas()

    title = str(post_data.get("image_title") or job.get("title") or "فرصة عمل جديدة").strip()
    category_font = _font(26, bold=True)
    label_font = _font(24, bold=True)
    org_font = _fit_font_for_box(
        draw,
        _value_or_missing(_display_organization(job)),
        Box(ORGANIZER_BOX.x + 28, ORGANIZER_BOX.y + 34, ORGANIZER_BOX.w - 56, 34),
        start=28,
        minimum=20,
        max_lines=1,
    )

    category = _category_label(job, post_data)
    announcement_label = _announcement_label(job)
    status_badge = str(job.get("deadline_status_reason") or "").strip()
    if status_badge.startswith("باقي ") or status_badge == "آخر يوم للترشيح":
        left_badge = status_badge
    else:
        left_badge = announcement_label
    draw.rounded_rectangle((724, 160, 958, 206), radius=23, fill="#071422")
    _draw_wrapped_center(draw, category, Box(742, 167, 198, 32), category_font, "#ffffff", max_lines=1)
    draw.rounded_rectangle((126, 160, 360, 206), radius=23, fill="#fff7ed", outline="#e6b25c", width=2)
    _draw_wrapped_center(draw, left_badge, Box(146, 167, 194, 32), category_font, "#8d5a13", max_lines=1)

    title_font = _fit_font_for_box(draw, title, TITLE_BOX, start=50, minimum=34, max_lines=3)
    _draw_wrapped_center(draw, title, TITLE_BOX, title_font, "#111820", line_spacing=12, max_lines=3)

    _draw_soft_shadow(draw, ORGANIZER_BOX, radius=18)
    draw.rounded_rectangle(
        (ORGANIZER_BOX.x, ORGANIZER_BOX.y, ORGANIZER_BOX.right, ORGANIZER_BOX.bottom),
        radius=18,
        fill="#f9fbfd",
        outline="#e1e6ec",
        width=2,
    )
    _draw_wrapped_right(
        draw,
        "الإدارة المنظمة",
        Box(ORGANIZER_BOX.x + 28, ORGANIZER_BOX.y + 12, ORGANIZER_BOX.w - 56, 24),
        label_font,
        "#08743f",
        max_lines=1,
    )
    _draw_wrapped_right(
        draw,
        _value_or_missing(_display_organization(job)),
        Box(ORGANIZER_BOX.x + 28, ORGANIZER_BOX.y + 44, ORGANIZER_BOX.w - 56, 34),
        org_font,
        "#111820",
        max_lines=1,
    )

    for box, (label, value) in zip(HIGHLIGHT_BOXES, _highlight_items(job)):
        _draw_highlight_box(draw, box, label, value)

    for box, (label, value) in zip(INFO_GRID_BOXES, _detail_items(job)):
        _draw_detail_box(draw, box, label, value)

    file_name = f"{job.get('source', 'job')}-{_safe_filename(str(job.get('job_id') or job.get('title')))}.png"
    output_path = OUTPUT_DIR / file_name
    image.convert("RGB").save(output_path, "PNG", optimize=True)
    LOGGER.info("Generated image: %s", output_path)
    return output_path
