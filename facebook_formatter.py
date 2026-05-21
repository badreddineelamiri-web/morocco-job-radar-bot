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
    "directeur": "مدير",
    "chef de division": "رئيس قسم",
    "chef de service": "رئيس مصلحة",
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
    if "fiche poste directeur" in lowered:
        return "منصب مدير"
    for needle, translated in JOB_TITLE_TRANSLATIONS.items():
        if needle in lowered:
            return translated
    if _arabic_ratio(title) >= 0.45:
        return title
    return "منصب جديد حسب الإعلان الرسمي" if is_official(job) else "عرض عمل جديد"


def _arabic_city(value: Any) -> str:
    city = _value(value)
    return CITY_TRANSLATIONS.get(city.lower(), city if _arabic_ratio(city) >= 0.4 else "غير مذكور")


def _arabic_source(value: Any) -> str:
    text = _value(value)
    return SOURCE_TRANSLATIONS.get(text, text)


def is_official(job: dict[str, Any]) -> bool:
    source_type = str(job.get("source_type") or "")
    return source_type in {"official_public", "official_ministry", "public_institution"}


def format_facebook_post(job: dict[str, Any]) -> dict[str, Any]:
    link = _value(job.get("application_url") or job.get("announcement_url") or job.get("url"), "")
    source_name = _arabic_source(job.get("source_name") or job.get("source"))
    title = str(job.get("seo_title") or "").strip() or _arabic_job_title(job)
    image_title = str(job.get("seo_title") or "").strip() or _arabic_job_title(job)

    if is_official(job):
        company = _arabic_source(job.get("organization") or job.get("company") or source_name)
        positions = _value(job.get("positions_count") or job.get("positions"))
        deadline = _value(job.get("deadline"))
        exam_date = _value(job.get("exam_date"))
        status = _value(job.get("deadline_status_reason"), "راجع آخر أجل داخل الإعلان")
        facebook_post = (
            f"{title}\n\n"
            f"الجهة المنظمة: {company}\n"
            f"عدد المناصب: {positions}\n"
            f"آخر أجل: {deadline}\n"
            f"تاريخ المباراة: {exam_date}\n\n"
            f"حالة الترشيح: {status}\n\n"
            "التفاصيل والرابط الرسمي في أول تعليق.\n"
            "تأكد من الشروط والوثائق داخل الإعلان قبل الترشح.\n\n"
            f"المصدر: {source_name}"
        )
        category = "مباراة توظيف"
    else:
        deadline_or_date = job.get("deadline") or job.get("publication_date") or job.get("published_at")
        facebook_post = (
            f"{title}\n\n"
            f"المشغل: {_value(job.get('company') or job.get('organization'))}\n"
            f"المدينة: {_arabic_city(job.get('city') or job.get('location'))}\n"
            f"عدد المناصب: {_value(job.get('positions_count') or job.get('positions'))}\n"
            f"آخر أجل أو تاريخ النشر: {_value(deadline_or_date)}\n\n"
            "طريقة التقديم والرابط في أول تعليق.\n"
            "راجع تفاصيل العرض قبل إرسال الترشيح.\n\n"
            f"المصدر: {source_name}"
        )
        category = "عرض عمل"

    first_comment = (
        "رابط التفاصيل أو التقديم:\n" + link
        if link
        else "رابط التفاصيل أو التقديم غير متوفر في المصدر."
    )
    if job.get("application_method"):
        first_comment += f"\n\nطريقة الترشيح: {job['application_method']}"

    return {
        "facebook_post": facebook_post,
        "first_comment": first_comment,
        "image_title": image_title[:90],
        "category": category,
        "hashtags": [],
        "source_url": link,
    }
