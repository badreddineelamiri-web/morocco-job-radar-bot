"""Publish generated job posts to a Facebook Page."""

from __future__ import annotations

import logging
import os
from pathlib import Path
import re
from typing import Any

import requests


LOGGER = logging.getLogger(__name__)
GRAPH_BASE_URL = "https://graph.facebook.com/v20.0"
REQUEST_TIMEOUT = 45


def _credentials() -> tuple[str, str]:
    page_id = os.getenv("FACEBOOK_PAGE_ID", "").strip()
    token = os.getenv("FACEBOOK_PAGE_ACCESS_TOKEN", "").strip()
    if not page_id or not token:
        raise RuntimeError("FACEBOOK_PAGE_ID or FACEBOOK_PAGE_ACCESS_TOKEN is missing.")
    return page_id, token


def _normalize_text(value: Any) -> str:
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in str(value or "").splitlines()]
    compact: list[str] = []
    blank_seen = False
    for line in lines:
        if line:
            compact.append(line)
            blank_seen = False
        elif not blank_seen:
            compact.append("")
            blank_seen = True
    return "\n".join(compact).strip()


def _normalize_publish_text(post_data: dict[str, Any]) -> tuple[str, str]:
    """Normalize caption and first comment text.
    
    Ensures the first comment contains the job application link.
    """
    caption = _normalize_text(post_data.get("facebook_post"))
    first_comment = _normalize_text(post_data.get("first_comment"))
    
    # Get all possible links
    source_link = _normalize_text(
        post_data.get("source_url") or 
        post_data.get("official_url") or 
        post_data.get("application_url") or
        post_data.get("url") or
        post_data.get("announcement_url")
    )

    # Default caption if empty
    if not caption:
        caption = "📢 فرصة عمل جديدة في المغرب! 🇲🇦\n\n🔗 التفاصيل أو رابط التقديم في أول تعليق ⬇️"
    
    # Ensure first comment has the link
    if source_link:
        if not first_comment:
            first_comment = f"🔗 رابط التقديم أو الإعلان الرسمي:\n{source_link}"
        elif source_link not in first_comment:
            # Check if first comment already mentions link
            if "رابط" not in first_comment and "link" not in first_comment.lower():
                first_comment = f"{first_comment}\n\n🔗 رابط التقديم أو الإعلان الرسمي:\n{source_link}"
            else:
                # Link might be there but not complete, append it
                if source_link not in first_comment:
                    first_comment = f"{first_comment}\n{source_link}"
    
    # If no link available, mention it in first comment
    if not source_link and not first_comment:
        first_comment = "🔗 رابط التقديم أو الإعلان الرسمي: غير مذكور في الإعلان"
    
    return caption, first_comment


def publish_job(post_data: dict[str, Any], image_path: Path) -> dict[str, Any]:
    caption, first_comment = _normalize_publish_text(post_data)

    if os.getenv("DRY_RUN", "").strip().lower() in {"1", "true", "yes"}:
        LOGGER.info("DRY_RUN enabled; Facebook publish skipped.")
        return {
            "ok": True,
            "dry_run": True,
            "image_path": str(image_path),
            "caption_preview": caption[:300],
            "first_comment_preview": first_comment[:300],
        }

    try:
        page_id, token = _credentials()
        with image_path.open("rb") as image_file:
            response = requests.post(
                f"{GRAPH_BASE_URL}/{page_id}/photos",
                data={"caption": caption, "published": "true", "access_token": token},
                files={"source": image_file},
                timeout=REQUEST_TIMEOUT,
            )
        response.raise_for_status()
        photo_data = response.json()
        photo_id = photo_data.get("id") or photo_data.get("post_id")
        LOGGER.info("Facebook photo uploaded: %s", photo_id)

        comment_data: dict[str, Any] = {}
        if photo_id and first_comment:
            comment_response = requests.post(
                f"{GRAPH_BASE_URL}/{photo_id}/comments",
                data={"message": first_comment, "access_token": token},
                timeout=REQUEST_TIMEOUT,
            )
            comment_response.raise_for_status()
            comment_data = comment_response.json()
            LOGGER.info("Facebook first comment posted: %s", comment_data.get("id"))

        return {"ok": True, "photo": photo_data, "comment": comment_data}
    except requests.RequestException as exc:
        message = exc.response.text if exc.response is not None else str(exc)
        LOGGER.error("Facebook publish failed: %s", message)
        return {"ok": False, "error": message}
    except RuntimeError as exc:
        LOGGER.error("Facebook credentials error: %s", exc)
        return {"ok": False, "error": str(exc)}
    except OSError as exc:
        LOGGER.error("Image file could not be read: %s", exc)
        return {"ok": False, "error": str(exc)}
