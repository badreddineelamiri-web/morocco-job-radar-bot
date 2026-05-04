"""Create polished square Facebook images for jobs with Pillow."""

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
except ImportError:  # pragma: no cover - only used when optional packages are unavailable.
    arabic_reshaper = None
    get_display = None


LOGGER = logging.getLogger(__name__)
ASSETS_DIR = Path("assets")
FONTS_DIR = ASSETS_DIR / "fonts"
OUTPUT_DIR = Path("data/generated_images")
TEMPLATE_PATH = ASSETS_DIR / "job_template.png"
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


TITLE_BOX = Box(82, 285, 916, 325)
SUMMARY_BOX = Box(95, 612, 565, 72)
REQUIREMENTS_BOX = Box(72, 708, 560, 224)
DETAILS_BOX = Box(682, 690, 322, 250)
LOGO_BOX = Box(792, 358, 176, 176)


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Get font for Arabic text rendering."""
    # Try custom fonts first
    font_names = (
        ["Cairo-Bold.ttf", "Tajawal-Bold.ttf", "NotoKufiArabic-Bold.ttf"]
        if bold
        else ["Cairo-Regular.ttf", "Tajawal-Regular.ttf", "NotoKufiArabic-Regular.ttf"]
    )
    candidates = [FONTS_DIR / name for name in font_names]
    
    # Try system fonts (Windows)
    system_fonts = [
        Path("C:/Windows/Fonts/arialbd.ttf") if bold else Path("C:/Windows/Fonts/arial.ttf"),
        Path("C:/Windows/Fonts/segoeuib.ttf") if bold else Path("C:/Windows/Fonts/segoeui.ttf"),
        Path("C:/Windows/Fonts/tahoma.ttf"),
        Path("C:/Windows/Fonts/calibri.ttf") if not bold else Path("C:/Windows/Fonts/calibrib.ttf"),
    ]
    candidates.extend(system_fonts)
    
    # Try Linux fonts
    candidates.extend([
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf") if bold 
        else Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        Path("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf") if bold
        else Path("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"),
    ])
    
    for path in candidates:
        try:
            if path.exists():
                return ImageFont.truetype(str(path), size=size)
        except OSError:
            continue
    
    # Fallback: use default font
    LOGGER.warning(f"Could not find suitable font, using default for size {size}")
    return ImageFont.load_default()


def _rtl(text: str) -> str:
    if arabic_reshaper is None or get_display is None:
        return text
    return get_display(arabic_reshaper.reshape(text))


def _text_size(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont) -> tuple[int, int]:
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0], bbox[3] - bbox[1]


def _wrap_pixels(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, max_width: int) -> list[str]:
    lines: list[str] = []
    for paragraph in str(text or "").splitlines() or [""]:
        words = paragraph.split()
        if not words:
            lines.append("")
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


def _draw_wrapped(
    draw: ImageDraw.ImageDraw,
    text: str,
    box: Box,
    font: ImageFont.ImageFont,
    fill: str,
    *,
    line_spacing: int = 10,
    align: str = "right",
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
        x = box.right - width if align == "right" else box.x
        draw.text((x, y), visual_line, font=font, fill=fill)
        y += height + line_spacing
    return y


def _draw_label_value(
    draw: ImageDraw.ImageDraw,
    label: str,
    value: Any,
    box: Box,
    y: int,
    label_font: ImageFont.ImageFont,
    value_font: ImageFont.ImageFont,
    color: str = "#263238",
) -> int:
    label_text = _rtl(label)
    label_width, label_height = _text_size(draw, label_text, label_font)
    draw.text((box.right - label_width, y), label_text, font=label_font, fill="#b32024")
    return _draw_wrapped(
        draw,
        _value_or_missing(value),
        Box(box.x, y + label_height + 8, box.w, max(36, box.bottom - y - label_height - 8)),
        value_font,
        color,
        line_spacing=6,
        max_lines=2,
    ) + 12


def _safe_filename(value: str) -> str:
    safe = "".join(char for char in value if char.isalnum() or char in ("-", "_")).strip()
    return safe[:80] or "job"


def _is_government_job(job: dict[str, Any]) -> bool:
    return job.get("job_type") == "government"


def _value_or_missing(value: Any) -> str:
    text = str(value).strip() if value else ""
    return text or "غير مذكور"


def _base_canvas() -> tuple[Image.Image, ImageDraw.ImageDraw]:
    if TEMPLATE_PATH.exists():
        image = Image.open(TEMPLATE_PATH).convert("RGBA")
        if image.size != (CANVAS_SIZE, CANVAS_SIZE):
            image = image.resize((CANVAS_SIZE, CANVAS_SIZE), Image.Resampling.LANCZOS)
    else:
        image = Image.new("RGBA", (CANVAS_SIZE, CANVAS_SIZE), "#f7f8fbff")
    return image, ImageDraw.Draw(image)


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


def _search_company_logo(company_name: str, job: dict[str, Any] | None = None) -> str | None:
    """Search for company logo using various methods."""
    if not company_name or company_name == "غير مذكور":
        return None
    
    # Try to construct domain from company name
    # Remove special characters and spaces, convert to lowercase
    import re
    clean_name = re.sub(r'[^\w\s]', '', company_name.lower())
    clean_name = re.sub(r'\s+', '', clean_name)
    
    # Common Moroccan company domains to try
    possible_domains = [
        f"{clean_name}.ma",
        f"{clean_name}.com",
        f"www.{clean_name}.ma",
        f"www.{clean_name}.com",
    ]
    
    # Add domain from job if available
    if job:
        for key in ['company_domain', 'domain', 'website', 'application_url', 'url']:
            url = str(job.get(key) or "")
            if url:
                from urllib.parse import urlparse
                parsed = urlparse(url if "://" in url else f"https://{url}")
                domain = parsed.netloc.lower().replace("www.", "")
                if domain:
                    possible_domains.insert(0, domain)
                    break
    
    # Try to search for company logo using Google Favicon service
    if possible_domains:
        return possible_domains[0]
    
    # Fallback: try to use company name directly with Clearbit
    if clean_name:
        return f"{clean_name}.com"
    
    return None


def _load_logo(job: dict[str, Any]) -> Image.Image | None:
    """Load company logo from various sources."""
    # 1. Try direct logo URL from job data
    logo_url = str(job.get("logo_url") or "").strip()
    if logo_url.startswith(("http://", "https://")):
        logo = _download_image(logo_url)
        if logo is not None:
            LOGGER.info(f"Loaded logo from direct URL: {logo_url}")
            return logo

    # 2. Try Clearbit API with domains from job
    for domain in _logo_domains(job):
        logo = _download_image(f"https://logo.clearbit.com/{domain}?size=128")
        if logo is not None:
            LOGGER.info(f"Loaded logo from Clearbit: {domain}")
            return logo
    
    # 3. Try to search for company logo using company name
    company = str(job.get("company") or "").strip()
    if company and company != "غير مذكور":
        # Try Google Favicon service as fallback
        domain = _search_company_logo(company, job)  # Pass job parameter
        if domain:
            # Try Clearbit with constructed domain
            logo = _download_image(f"https://logo.clearbit.com/{domain}?size=128")
            if logo is not None:
                LOGGER.info(f"Loaded logo from constructed domain: {domain}")
                return logo
            
            # Try favicon as last resort
            logo = _download_image(f"https://www.google.com/s2/favicons?domain={domain}&sz=128")
            if logo is not None:
                LOGGER.info(f"Loaded favicon for: {domain}")
                return logo
    
    LOGGER.debug(f"No logo found for company: {company}")
    return None


def _fit_image(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    fitted = image.copy()
    fitted.thumbnail(size, Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", size, (255, 255, 255, 0))
    x = (size[0] - fitted.width) // 2
    y = (size[1] - fitted.height) // 2
    canvas.alpha_composite(fitted, (x, y))
    return canvas


def _company_initials(company: str) -> str:
    words = [word for word in re.split(r"\s+", company.strip()) if word]
    if not words:
        return "JOB"
    latin = [word[0].upper() for word in words if word[0].isascii() and word[0].isalnum()]
    if latin:
        return "".join(latin[:3])
    return "".join(word[0] for word in words[:2])


def _draw_logo_badge(draw: ImageDraw.ImageDraw, company: str, box: Box) -> None:
    draw.rounded_rectangle((box.x, box.y, box.right, box.bottom), radius=28, fill="#ffffff", outline="#e5e0d7", width=3)
    initials = _rtl(_company_initials(company))
    font = _font(44, bold=True)
    width, height = _text_size(draw, initials, font)
    draw.text(
        (box.x + (box.w - width) // 2, box.y + (box.h - height) // 2 - 2),
        initials,
        font=font,
        fill="#116b43",
    )


def _paste_logo(image: Image.Image, draw: ImageDraw.ImageDraw, job: dict[str, Any]) -> None:
    company = _value_or_missing(job.get("company"))
    draw.rounded_rectangle(
        (LOGO_BOX.x - 10, LOGO_BOX.y - 10, LOGO_BOX.right + 10, LOGO_BOX.bottom + 10),
        radius=34,
        fill="#fffffff0",
        outline="#eee8dd",
        width=2,
    )
    logo = _load_logo(job)
    if logo is None:
        _draw_logo_badge(draw, company, LOGO_BOX)
        return
    image.alpha_composite(_fit_image(logo, (LOGO_BOX.w, LOGO_BOX.h)), (LOGO_BOX.x, LOGO_BOX.y))


def _requirements(job: dict[str, Any]) -> list[str]:
    raw = job.get("requirements") or job.get("skills") or []
    if isinstance(raw, str):
        items = [item.strip(" -•\t") for item in re.split(r"[\n;|،]+", raw) if item.strip(" -•\t")]
    elif isinstance(raw, list):
        items = [str(item).strip() for item in raw if str(item).strip()]
    else:
        items = []

    if not items:
        tags = job.get("tags") if isinstance(job.get("tags"), list) else []
        items = [str(tag).strip() for tag in tags if str(tag).strip()]
    if not items and job.get("description"):
        words = str(job["description"]).strip()
        items = [words[:120] + ("..." if len(words) > 120 else "")]
    return items[:4] or ["راجع الإعلان الرسمي لمعرفة الشروط الكاملة"]


def _draw_title_area(draw: ImageDraw.ImageDraw, job: dict[str, Any], post_data: dict[str, Any]) -> None:
    title_font = _font(44, bold=True)
    meta_font = _font(27)
    source_font = _font(25, bold=True)

    title = str(post_data.get("image_title") or job.get("title") or "فرصة عمل جديدة").strip()
    _draw_wrapped(draw, title, TITLE_BOX, title_font, "#17212b", line_spacing=12, max_lines=4)

    summary_parts = [
        f"المؤسسة: {_value_or_missing(job.get('company'))}",
        f"المدينة: {_value_or_missing(job.get('location'))}",
    ]
    if _is_government_job(job):
        summary_parts.append(f"عدد المناصب: {_value_or_missing(job.get('positions'))}")
    elif job.get("remote"):
        summary_parts.append("نمط العمل: عن بعد")
    _draw_wrapped(draw, " | ".join(summary_parts), SUMMARY_BOX, meta_font, "#44515c", line_spacing=8, max_lines=2)

    badge = "مصدر رسمي مغربي" if _is_government_job(job) else "فرصة عمل جديدة"
    badge_text = _rtl(badge)
    badge_width, badge_height = _text_size(draw, badge_text, source_font)
    x = TITLE_BOX.right - badge_width
    y = TITLE_BOX.y + TITLE_BOX.h - badge_height
    draw.text((x, y), badge_text, font=source_font, fill="#116b43")


def _draw_requirements(draw: ImageDraw.ImageDraw, job: dict[str, Any]) -> None:
    heading_font = _font(30, bold=True)
    body_font = _font(26)
    heading = _rtl("المتطلبات الأساسية")
    heading_width, _ = _text_size(draw, heading, heading_font)
    draw.text((REQUIREMENTS_BOX.right - heading_width, REQUIREMENTS_BOX.y), heading, font=heading_font, fill="#116b43")

    y = REQUIREMENTS_BOX.y + 48
    for item in _requirements(job):
        if y >= REQUIREMENTS_BOX.bottom - 24:
            break
        bullet = "•"
        bullet_width, _ = _text_size(draw, bullet, body_font)
        draw.text((REQUIREMENTS_BOX.right - bullet_width, y), bullet, font=body_font, fill="#b32024")
        y = _draw_wrapped(
            draw,
            item,
            Box(REQUIREMENTS_BOX.x, y, REQUIREMENTS_BOX.w - 28, REQUIREMENTS_BOX.bottom - y),
            body_font,
            "#263238",
            line_spacing=6,
            max_lines=2,
        ) + 8


def _draw_details(draw: ImageDraw.ImageDraw, job: dict[str, Any]) -> None:
    label_font = _font(25, bold=True)
    value_font = _font(26)
    y = DETAILS_BOX.y
    y = _draw_label_value(draw, "الشركة/المؤسسة", job.get("company"), DETAILS_BOX, y, label_font, value_font)
    y = _draw_label_value(draw, "المدينة", job.get("location"), DETAILS_BOX, y, label_font, value_font)

    if _is_government_job(job):
        detail_label = "آخر أجل"
        detail_value = job.get("deadline")
    else:
        detail_label = "نمط العمل"
        detail_value = "عن بعد" if job.get("remote") else "حسب الإعلان"
    _draw_label_value(draw, detail_label, detail_value, DETAILS_BOX, y, label_font, value_font)


def create_job_image(job: dict[str, Any], post_data: dict[str, Any]) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    image, draw = _base_canvas()

    _paste_logo(image, draw, job)
    _draw_title_area(draw, job, post_data)
    _draw_requirements(draw, job)
    _draw_details(draw, job)

    file_name = f"{job.get('source', 'job')}-{_safe_filename(str(job.get('job_id') or job.get('title')))}.png"
    output_path = OUTPUT_DIR / file_name
    image.convert("RGB").save(output_path, "PNG", optimize=True)
    LOGGER.info("Generated image: %s", output_path)
    return output_path
