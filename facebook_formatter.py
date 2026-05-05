"""Deterministic Facebook post formatting for dry-run and publishing."""

from __future__ import annotations

from typing import Any


def _value(value: Any, fallback: str = "غير مذكور") -> str:
    text = str(value or "").strip()
    return text or fallback


def is_official(job: dict[str, Any]) -> bool:
    source_type = str(job.get("source_type") or "")
    return source_type in {"official_public", "official_ministry", "public_institution"}


def format_facebook_post(job: dict[str, Any]) -> dict[str, Any]:
    link = _value(job.get("application_url") or job.get("announcement_url") or job.get("url"), "")
    source_name = _value(job.get("source_name") or job.get("source"))
    if is_official(job):
        facebook_post = (
            "📢 مباراة توظيف رسمية بالمغرب\n\n"
            f"المنصب: {_value(job.get('job_title') or job.get('title'))}\n"
            f"الإدارة المنظمة: {_value(job.get('organization') or job.get('company'))}\n"
            f"عدد المناصب: {_value(job.get('positions_count') or job.get('positions'))}\n"
            f"آخر أجل للترشيح: {_value(job.get('deadline'))}\n"
            f"تاريخ المباراة: {_value(job.get('exam_date'))}\n\n"
            "رابط التفاصيل والتقديم في أول تعليق.\n\n"
            "تابع الصفحة للمزيد من مباريات التوظيف بالمغرب.\n\n"
            f"المصدر: {source_name}"
        )
        category = "مباراة توظيف رسمية"
    else:
        deadline_or_date = job.get("deadline") or job.get("publication_date") or job.get("published_at")
        facebook_post = (
            "📢 عرض عمل جديد بالمغرب\n\n"
            f"المنصب: {_value(job.get('job_title') or job.get('title'))}\n"
            f"الشركة/المشغل: {_value(job.get('company') or job.get('organization'))}\n"
            f"المدينة: {_value(job.get('city') or job.get('location'))}\n"
            f"عدد المناصب: {_value(job.get('positions_count') or job.get('positions'))}\n"
            f"آخر أجل أو تاريخ النشر: {_value(deadline_or_date)}\n\n"
            "رابط التفاصيل أو طريقة الترشيح في أول تعليق.\n\n"
            "تابع الصفحة للمزيد من فرص العمل بالمغرب.\n\n"
            f"المصدر: {source_name}"
        )
        category = "عرض عمل"

    first_comment = "رابط التفاصيل أو التقديم:\n" + link if link else "رابط التفاصيل أو التقديم غير متوفر."
    if job.get("application_method"):
        first_comment += f"\n\nطريقة الترشيح: {job['application_method']}"
    return {
        "facebook_post": facebook_post,
        "first_comment": first_comment,
        "image_title": _value(job.get("job_title") or job.get("title"))[:90],
        "category": category,
        "hashtags": [],
        "source_url": link,
    }
