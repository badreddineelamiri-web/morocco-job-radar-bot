"""Classify Moroccan job announcements before publishing."""

from __future__ import annotations

import datetime as dt
import re
from typing import Any

from date_parser import parse_date


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

RESULT_WORDS = (
    "نتيجة",
    "نتائج",
    "النتائج",
    "الناجحين",
    "الناجحات",
    "النجاح",
    "النهائية",
    "لائحة الانتظار",
    "liste d'attente",
    "resultat",
    "résultat",
    "resultats",
    "résultats",
    "admis",
    "admissibles",
)

CALL_LIST_WORDS = (
    "لائحة المدعوين",
    "لوائح المدعوين",
    "لائحة المترشحين",
    "لوائح المترشحين",
    "المقبولين لاجتياز",
    "المدعوين لاجتياز",
    "استدعاء",
    "استدعاءات",
    "شفوي",
    "الشفوي",
    "كتابي",
    "الكتابي",
    "الفحص الطبي",
    "الاختبار البسيكوتقني",
    "liste des candidats",
    "liste candidats",
    "convocation",
    "convoques",
    "convoqués",
    "oral",
    "ecrit",
    "écrit",
)

OPENING_WORDS = (
    "مباراة توظيف",
    "مباريات توظيف",
    "إعلان توظيف",
    "اعلان توظيف",
    "تنظيم مباراة",
    "إجراء مباراة",
    "اجراء مباراة",
    "توظيف",
    "منصب",
    "مناصب",
    "concours de recrutement",
    "avis de concours",
    "recrutement",
    "appel à candidature",
    "appel a candidature",
)

TRAINING_WORDS = (
    "ولوج",
    "التكوين",
    "تكوين",
    "التسجيل",
    "معاهد",
    "مؤسسات التكوين",
    "منحة",
    "bourse",
    "formation",
)


def _text(job: dict[str, Any]) -> str:
    return " ".join(
        str(job.get(key) or "")
        for key in (
            "title",
            "job_title",
            "description",
            "organization",
            "company",
            "source",
            "source_name",
        )
    ).lower()


def arabic_source(value: Any) -> str:
    text = str(value or "").strip()
    return SOURCE_TRANSLATIONS.get(text, text)


def announcement_kind(job: dict[str, Any]) -> tuple[str, str]:
    text = _text(job)
    if any(word in text for word in RESULT_WORDS):
        return "result", "نتائج مباراة وليست إعلان ترشيح"
    if any(word in text for word in CALL_LIST_WORDS):
        return "call_list", "لائحة أو استدعاء وليست إعلان ترشيح"
    if any(word in text for word in TRAINING_WORDS) and "توظيف" not in text and "recrutement" not in text:
        return "training", "إعلان تكوين أو ولوج"
    if any(word in text for word in OPENING_WORDS):
        return "job_opening", "إعلان توظيف مفتوح"
    return "unknown", "نوع الإعلان غير واضح"


def deadline_status(job: dict[str, Any], today: dt.date | None = None) -> tuple[str, str]:
    today = today or dt.date.today()
    deadline = parse_date(str(job.get("deadline") or ""))
    if not deadline:
        return "unknown_deadline", "آخر أجل غير مذكور"
    if deadline < today:
        return "expired", f"انتهى أجل الترشيح: {deadline.isoformat()}"
    days_left = (deadline - today).days
    if days_left == 0:
        return "last_day", "آخر يوم للترشيح"
    return "open", f"باقي {days_left} يوم"


def _clean_title(title: str) -> str:
    text = re.sub(r"\s+", " ", str(title or "")).strip(" -–")
    replacements = {
        "Fiche poste Directeur": "منصب مدير",
        "fiche poste directeur": "منصب مدير",
        "Avis de concours de recrutement": "مباراة توظيف",
        "Concours de recrutement": "مباراة توظيف",
    }
    for source, target in replacements.items():
        text = text.replace(source, target)
    return text or "إعلان توظيف"


def seo_title(job: dict[str, Any]) -> str:
    title = _clean_title(str(job.get("title") or job.get("job_title") or ""))
    org = arabic_source(job.get("organization") or job.get("company") or job.get("source_name") or job.get("source"))
    positions = str(job.get("positions_count") or job.get("positions") or "").strip()
    kind, _ = announcement_kind(job)

    if kind == "training":
        return f"إعلان التسجيل في {title}"[:120]
    if kind == "result":
        return f"نتائج {title}"[:120]
    if kind == "call_list":
        return f"لوائح المدعوين لاجتياز {title}"[:120]
    if positions:
        return f"مباراة توظيف {positions} منصب ب{org}"[:120]
    if "مباراة" in title or "توظيف" in title:
        return f"{title} ب{org}"[:120]
    return f"إعلان توظيف: {title} ب{org}"[:120]


def apply_job_metadata(job: dict[str, Any], today: dt.date | None = None) -> dict[str, Any]:
    kind, kind_reason = announcement_kind(job)
    status, status_reason = deadline_status(job, today=today)
    labels = {
        "job_opening": "مباراة مفتوحة",
        "training": "تكوين/ولوج",
        "result": "نتائج",
        "call_list": "لوائح المدعوين",
        "unknown": "غير مصنف",
    }
    job["announcement_kind"] = kind
    job["announcement_kind_reason"] = kind_reason
    job["deadline_status"] = status
    job["deadline_status_reason"] = status_reason
    job["announcement_type_label"] = labels.get(kind, "غير مصنف")
    job["seo_title"] = seo_title(job)
    return job
