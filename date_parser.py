"""Parse Moroccan job dates written in French, Arabic, or numeric forms."""

from __future__ import annotations

import datetime as dt
import re
import unicodedata


FRENCH_MONTHS = {
    "janvier": 1,
    "fevrier": 2,
    "février": 2,
    "mars": 3,
    "avril": 4,
    "mai": 5,
    "juin": 6,
    "juillet": 7,
    "aout": 8,
    "août": 8,
    "septembre": 9,
    "octobre": 10,
    "novembre": 11,
    "decembre": 12,
    "décembre": 12,
}

ARABIC_MONTHS = {
    "يناير": 1,
    "فبراير": 2,
    "مارس": 3,
    "أبريل": 4,
    "ابريل": 4,
    "ماي": 5,
    "مايو": 5,
    "يونيو": 6,
    "يونيه": 6,
    "يوليوز": 7,
    "يوليو": 7,
    "غشت": 8,
    "أغسطس": 8,
    "اغسطس": 8,
    "شتنبر": 9,
    "سبتمبر": 9,
    "أكتوبر": 10,
    "اكتوبر": 10,
    "نونبر": 11,
    "نوفمبر": 11,
    "دجنبر": 12,
    "ديسمبر": 12,
}

MONTH_PATTERN = "|".join(sorted([*FRENCH_MONTHS, *ARABIC_MONTHS], key=len, reverse=True))
DATE_RE = re.compile(
    rf"(\d{{4}}[/-]\d{{1,2}}[/-]\d{{1,2}}|\d{{1,2}}[/-]\d{{1,2}}[/-]\d{{2,4}}|\d{{1,2}}\s+(?:{MONTH_PATTERN})\s+\d{{4}})",
    re.IGNORECASE,
)


def _clean(value: str) -> str:
    text = unicodedata.normalize("NFKC", str(value or ""))
    return re.sub(r"\s+", " ", text).strip()


def extract_date_text(value: str) -> str:
    match = DATE_RE.search(_clean(value))
    return match.group(1) if match else ""


def parse_date(value: str | None) -> dt.date | None:
    text = extract_date_text(value or "")
    if not text:
        return None
    text = _clean(text)

    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d/%m/%Y", "%d-%m-%Y", "%d/%m/%y", "%d-%m-%y"):
        try:
            return dt.datetime.strptime(text, fmt).date()
        except ValueError:
            pass

    match = re.match(rf"(\d{{1,2}})\s+({MONTH_PATTERN})\s+(\d{{4}})", text, re.IGNORECASE)
    if not match:
        return None
    day = int(match.group(1))
    month_name = match.group(2).lower()
    month = FRENCH_MONTHS.get(month_name) or ARABIC_MONTHS.get(month_name)
    if not month:
        return None
    try:
        return dt.date(int(match.group(3)), month, day)
    except ValueError:
        return None
