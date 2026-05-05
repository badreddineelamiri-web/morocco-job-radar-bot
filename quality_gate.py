"""Quality checks that run before Facebook publishing."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PIL import Image


MOJIBAKE_MARKERS = ("Ø", "Ù", "Ã", "ðŸ", "�")


def _arabic_ratio(text: str) -> float:
    letters = [char for char in text if char.isalpha()]
    if not letters:
        return 0.0
    arabic = [char for char in letters if "\u0600" <= char <= "\u06ff"]
    return len(arabic) / len(letters)


def validate_post_quality(post_data: dict[str, Any]) -> tuple[bool, str]:
    caption = str(post_data.get("facebook_post") or "")
    first_comment = str(post_data.get("first_comment") or "")
    image_title = str(post_data.get("image_title") or "")
    combined = "\n".join([caption, first_comment, image_title])

    if any(marker in combined for marker in MOJIBAKE_MARKERS):
        return False, "post text contains broken encoding markers"
    if _arabic_ratio(caption) < 0.55:
        return False, "caption is not Arabic enough"
    if "http://" not in first_comment and "https://" not in first_comment:
        return False, "first comment is missing the details link"
    if len(caption.strip()) < 80:
        return False, "caption is too short"
    return True, "post quality accepted"


def validate_image_quality(image_path: Path) -> tuple[bool, str]:
    if not image_path.exists():
        return False, "image was not created"
    if image_path.stat().st_size < 20_000:
        return False, "image file is unexpectedly small"
    try:
        with Image.open(image_path) as image:
            width, height = image.size
    except OSError as exc:
        return False, f"image cannot be opened: {exc}"
    if width < 1000 or height < 1000:
        return False, f"image dimensions are too small: {width}x{height}"
    return True, "image quality accepted"
