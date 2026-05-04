"""AI writer for professional Arabic Facebook job posts."""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any

from modules.ai_providers import generate_json_text


LOGGER = logging.getLogger(__name__)


def _is_government_job(job: dict[str, Any]) -> bool:
    return job.get("job_type") == "government"


def _fallback_hashtags(job: dict[str, Any]) -> list[str]:
    if _is_government_job(job):
        return [
            "#مباريات_التوظيف",
            "#الوظيفة_العمومية",
            "#وظائف_المغرب",
            "#Concours_Maroc",
            "#Emploi_Public",
            "#توظيف",
        ]

    hashtags = ["#وظائف_المغرب", "#فرص_عمل", "#توظيف", "#Recrutement", "#MoroccoJobs"]
    if job.get("remote"):
        hashtags.append("#عمل_عن_بعد")
    title_word = str(job.get("title", "")).split(" ")[0].strip("#,.;:،") or ""
    if title_word and title_word.isascii():
        hashtags.append(f"#{title_word}")
    return hashtags[:10]


def _value_or_missing(value: Any) -> str:
    text = str(value).strip() if value else ""
    return text or "غير مذكور"


def _application_link(job: dict[str, Any]) -> str:
    return str(job.get("application_url") or job.get("announcement_url") or job.get("url") or "").strip()


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
        description = re.sub(r"\s+", " ", str(job["description"])).strip()
        if description:
            items = [description[:140] + ("..." if len(description) > 140 else "")]
    return items[:3] or ["يرجى مراجعة الإعلان الرسمي لمعرفة الشروط والوثائق المطلوبة."]


def _requirements_block(job: dict[str, Any]) -> str:
    return "\n".join(f"- {item}" for item in _requirements(job))


def _why_this_job(job: dict[str, Any]) -> str:
    if _is_government_job(job):
        return "فرصة مناسبة للمهتمين بالعمل في القطاع العمومي، مع ضرورة مراجعة الإعلان الرسمي للتأكد من الشروط والآجال."
    if job.get("remote"):
        return "فرصة مرنة قد تناسب الباحثين عن عمل عن بعد أو تجربة مهنية أوسع داخل سوق الشغل."
    return "فرصة تستحق الاطلاع إذا كانت خبرتك أو اهتماماتك قريبة من متطلبات المنصب."


def _first_comment(job: dict[str, Any]) -> str:
    link = _application_link(job)
    if link:
        return f"رابط التقديم أو الإعلان الرسمي:\n{link}"
    return "رابط التقديم أو الإعلان الرسمي: غير مذكور في المصدر."


def fallback_government_post(job: dict[str, Any]) -> dict[str, Any]:
    hashtags = _fallback_hashtags(job)
    title = _value_or_missing(job.get("title"))
    company = _value_or_missing(job.get("company"))
    location = _value_or_missing(job.get("location"))
    positions = _value_or_missing(job.get("positions"))
    deadline = _value_or_missing(job.get("deadline"))

    facebook_post = (
        "فرصة عمل جديدة في المغرب\n\n"
        "التفاصيل:\n"
        f"- المنصب: {title}\n"
        f"- الشركة / المؤسسة: {company}\n"
        f"- المدينة: {location}\n"
        f"- عدد المناصب: {positions}\n"
        f"- آخر أجل: {deadline}\n\n"
        "المتطلبات الأساسية:\n"
        f"{_requirements_block(job)}\n\n"
        "لماذا هذه الفرصة؟\n"
        f"{_why_this_job(job)}\n\n"
        "للتقديم والاطلاع على التفاصيل، الرابط الرسمي موجود في أول تعليق.\n\n"
        + " ".join(hashtags)
    )
    return {
        "facebook_post": facebook_post,
        "first_comment": _first_comment(job),
        "image_title": title[:90],
        "category": "مباراة توظيف",
        "hashtags": hashtags,
    }


def fallback_private_post(job: dict[str, Any]) -> dict[str, Any]:
    hashtags = _fallback_hashtags(job)
    title = _value_or_missing(job.get("title"))
    company = _value_or_missing(job.get("company"))
    location = _value_or_missing(job.get("location"))
    remote_label = "عن بعد" if job.get("remote") else "حضوري أو حسب إعلان الشركة"

    facebook_post = (
        "فرصة عمل جديدة في المغرب\n\n"
        "التفاصيل:\n"
        f"- المنصب: {title}\n"
        f"- الشركة / المؤسسة: {company}\n"
        f"- المدينة: {location}\n"
        f"- نمط العمل: {remote_label}\n\n"
        "المتطلبات الأساسية:\n"
        f"{_requirements_block(job)}\n\n"
        "لماذا هذه الفرصة؟\n"
        f"{_why_this_job(job)}\n\n"
        "للتقديم والاطلاع على التفاصيل، الرابط الرسمي موجود في أول تعليق.\n\n"
        + " ".join(hashtags)
    )
    return {
        "facebook_post": facebook_post,
        "first_comment": _first_comment(job),
        "image_title": title[:90],
        "category": "وظائف",
        "hashtags": hashtags,
    }


def fallback_post(job: dict[str, Any]) -> dict[str, Any]:
    return fallback_government_post(job) if _is_government_job(job) else fallback_private_post(job)


def _extract_json(text: str) -> dict[str, Any]:
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            raise
        return json.loads(match.group(0))


def _normalize_whitespace(text: str) -> str:
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in str(text or "").splitlines()]
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


def _validate_ai_response(data: dict[str, Any], job: dict[str, Any]) -> dict[str, Any]:
    fallback = fallback_post(job)
    required = ["facebook_post", "first_comment", "image_title", "category", "hashtags"]
    for key in required:
        if key not in data:
            raise ValueError(f"AI response missing {key}")
    if not isinstance(data["hashtags"], list):
        data["hashtags"] = fallback["hashtags"]

    link = _application_link(job)
    data["facebook_post"] = _normalize_whitespace(str(data.get("facebook_post") or fallback["facebook_post"]))
    data["first_comment"] = _normalize_whitespace(str(data.get("first_comment") or _first_comment(job)))
    data["image_title"] = str(data.get("image_title") or fallback["image_title"]).strip()[:90]
    if link and link not in data["first_comment"]:
        data["first_comment"] = f"{data['first_comment']}\n{link}".strip()
    return data


def _job_prompt(job: dict[str, Any]) -> str:
    template = (
        "اكتب منشور فيسبوك عربي واضح ومهني لجمهور مغربي عن فرصة العمل التالية. "
        "استعمل العربية الفصحى البسيطة، واجعل المنشور منظما وسهل القراءة. "
        "لا تخترع الراتب أو الآجال أو الشروط غير الموجودة في بيانات الوظيفة. "
        "ضع رابط التقديم أو الإعلان الرسمي في first_comment فقط، ولا تضعه داخل facebook_post. "
        "اجعل image_title قصيرا وقويا لأنه سيظهر بخط كبير على الصورة. "
        "أعد JSON صالحا فقط بالمفاتيح: facebook_post, first_comment, image_title, category, hashtags."
    )
    if _is_government_job(job):
        template += " هذه وظيفة أو مباراة من مصدر رسمي، لذلك أكّد ضرورة مراجعة الإعلان الرسمي قبل التقديم."
    return f"{template}\n\nJOB JSON:\n{json.dumps(job, ensure_ascii=False)}"


def generate_post(job: dict[str, Any]) -> dict[str, Any]:
    """Generate Facebook post using AI, with a clean Arabic fallback."""
    system_prompt = (
        "أنت محرر توظيف محترف تكتب بالعربية الفصحى لجمهور مغربي. "
        "كن واضحا ومنظما وصادقا. أعد JSON صالحا فقط دون أي نص خارجه."
    )

    forced_provider = os.getenv("AI_FACEBOOK_PROVIDER", "groq")

    original_provider = os.getenv("AI_PROVIDER", "auto")
    try:
        os.environ["AI_PROVIDER"] = forced_provider
        content = generate_json_text(system_prompt, _job_prompt(job), task="facebook")

        if not content:
            LOGGER.warning("No AI provider returned content; using fallback Arabic template.")
            return fallback_post(job)
        return _validate_ai_response(_extract_json(content), job)
    except (KeyError, IndexError, ValueError, json.JSONDecodeError) as exc:
        LOGGER.error("AI writing failed; using fallback template: %s", exc)
        return fallback_post(job)
    finally:
        os.environ["AI_PROVIDER"] = original_provider
