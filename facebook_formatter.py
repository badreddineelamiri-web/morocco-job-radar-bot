"""Deterministic Arabic Facebook post formatting."""

from __future__ import annotations

from typing import Any


JOB_TITLE_TRANSLATIONS = {
    "caissier": "أمين صندوق",
    "caissiere": "أمينة صندوق",
    "employe de gestion administrative": "موظف في التدبير الإداري",
    "employé de gestion administrative": "موظف في التدبير الإداري",
    "commercial": "مكلف تجاري",
    "gardien-concierge": "حارس ومكلف بالاستقبال",
    "technicien": "تقني",
    "ingenieur": "مهندس",
    "ingénieur": "مهندس",
    "assistant": "مساعد",
    "assistante": "مساعدة",
    "maitre de conferences": "أستاذ محاضر",
    "maître de conférences": "أستاذ محاضر",
    "adjoint technique": "مساعد تقني",
    "architecte": "مهندس معماري",
    "inspecteur du travail": "مفتش الشغل",
}

CITY_TRANSLATIONS = {
    "casa-nouacer": "الدار البيضاء - النواصر",
    "casablanca": "الدار البيضاء",
    "rabat": "الرباط",
    "marrakech": "مراكش",
    "tanger": "طنجة",
    "fes": "فاس",
    "fès": "فاس",
    "agadir": "أكادير",
    "essaouira": "الصويرة",
    "sale": "سلا",
    "salé": "سلا",
    "kenitra": "القنيطرة",
    "oujda": "وجدة",
    "meknes": "مكناس",
    "el jadida": "الجديدة",
}


def _value(value: Any, fallback: str = "غير مذكور") -> str:
    text = str(value or "").strip()
    return text or fallback


def _arabic_ratio(text: str) -> float:
    letters = [char for char in text if char.isalpha()]
    if not letters:
        return 0.0
    arabic = [char for char in letters if "\u0600" <= char <= "\u06ff"]
    return len(arabic) / len(letters)


def _strip_source_noise(text: str) -> str:
    import re

    text = re.sub(r"\b[A-Z]{1,3}\.?\d{6,}\b", "", text)
    text = re.sub(r"\(\d+\)", "", text)
    text = re.sub(r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b", "", text)
    return " ".join(text.split()).strip(" -")


def _arabic_job_title(job: dict[str, Any]) -> str:
    title = _strip_source_noise(_value(job.get("job_title") or job.get("title"), ""))
    lowered = title.lower()
    for needle, translated in JOB_TITLE_TRANSLATIONS.items():
        if needle in lowered:
            return translated
    if _arabic_ratio(title) >= 0.45:
        return title
    return "منصب جديد حسب الإعلان الرسمي" if is_official(job) else "عرض عمل جديد"


def _arabic_city(value: Any) -> str:
    city = _value(value)
    return CITY_TRANSLATIONS.get(city.lower(), city if _arabic_ratio(city) >= 0.4 else "غير مذكور")


def is_official(job: dict[str, Any]) -> bool:
    source_type = str(job.get("source_type") or "")
    return source_type in {"official_public", "official_ministry", "public_institution"}


def format_facebook_post(job: dict[str, Any]) -> dict[str, Any]:
    link = _value(job.get("application_url") or job.get("announcement_url") or job.get("url"), "")
    source_name = _value(job.get("source_name") or job.get("source"))
    title = _arabic_job_title(job)

    if is_official(job):
        facebook_post = (
            "مباراة توظيف رسمية بالمغرب\n\n"
            f"المنصب: {title}\n"
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
            "عرض عمل جديد بالمغرب\n\n"
            f"المنصب: {title}\n"
            f"الشركة أو المشغل: {_value(job.get('company') or job.get('organization'))}\n"
            f"المدينة: {_arabic_city(job.get('city') or job.get('location'))}\n"
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
        "image_title": title[:90],
        "category": category,
        "hashtags": [],
        "source_url": link,
    }
