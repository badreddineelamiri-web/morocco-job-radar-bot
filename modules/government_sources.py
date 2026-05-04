"""Fetch official Moroccan government and agency job sources.

These websites do not expose a stable public API, so this module uses careful
HTML parsing with defensive fallbacks. If a page layout changes, the bot logs
the issue, skips weak entries, and continues with the next source.
"""

from __future__ import annotations

import hashlib
import datetime
import json
import logging
import os
import re
import warnings
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup, Tag
from requests import Session
from requests.adapters import HTTPAdapter
from urllib3.exceptions import InsecureRequestWarning
from urllib3.util.retry import Retry


LOGGER = logging.getLogger(__name__)
CONFIG_PATH = Path("config/government_sources.json")
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "5"))
USER_AGENT = (
    "MoroccoJobRadarBot/1.0 "
    "(official-job-monitor; contact: configure-your-email@example.com)"
)
OPEN_DATA_PACKAGE_SEARCH_URL = "https://data.gov.ma/data/api/3/action/package_search?q=emploi%20public"


def _session() -> Session:
    session = requests.Session()
    retry = Retry(
        total=0,
        connect=0,
        read=0,
        backoff_factor=0.8,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET",),
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


HTTP = _session()
warnings.filterwarnings("ignore", category=InsecureRequestWarning)


def _clean_text(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"\s+", " ", value).strip()


def _hash_id(*parts: str) -> str:
    raw = "|".join(_clean_text(part).lower() for part in parts if part)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:20]


def _load_sources() -> list[dict[str, Any]]:
    try:
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        return [item for item in data if item.get("enabled", True)]
    except (OSError, json.JSONDecodeError) as exc:
        LOGGER.error("Could not load government sources config: %s", exc)
        return []


def _candidate_urls(url: str) -> list[str]:
    """Return fetch candidates for official sites with fragile HTTPS setups."""
    candidates = [url]
    parsed = urlparse(url)
    if parsed.scheme == "https":
        http_url = parsed._replace(scheme="http").geturl()
        if http_url not in candidates:
            candidates.append(http_url)
    return candidates


def _request_get(url: str) -> requests.Response | None:
    headers = {"User-Agent": USER_AGENT, "Accept-Language": "ar,fr;q=0.9,en;q=0.7"}
    last_error: Exception | None = None
    for candidate in _candidate_urls(url):
        for verify in (True, False):
            try:
                response = HTTP.get(
                    candidate,
                    headers=headers,
                    timeout=REQUEST_TIMEOUT,
                    allow_redirects=True,
                    verify=verify,
                )
                response.raise_for_status()
                return response
            except requests.exceptions.SSLError as exc:
                last_error = exc
                if verify:
                    LOGGER.warning(
                        "HTTPS certificate issue for %s; retrying without strict verification.",
                        candidate,
                    )
                    continue
                break
            except requests.RequestException as exc:
                last_error = exc
                break
    LOGGER.error("Official source failed, skipping %s: %s", url, last_error)
    return None


def _get_soup(url: str) -> BeautifulSoup | None:
    response = _request_get(url)
    if response is None:
        return None
    if response.encoding is None:
        response.encoding = response.apparent_encoding
    return BeautifulSoup(response.text, "html.parser")


def _get_json(url: str) -> dict[str, Any] | None:
    try:
        response = _request_get(url)
        if response is None:
            return None
        data = response.json()
        return data if isinstance(data, dict) else None
    except ValueError as exc:
        LOGGER.error("Official JSON source returned invalid JSON, skipping %s: %s", url, exc)
        return None


def fetch_open_data_resources() -> list[dict[str, Any]]:
    """Discover official emploi-public datasets from data.gov.ma CKAN API.

    These records are useful as official references, but they are not live job
    postings. The bot logs them and keeps live publishing based on
    emploi-public.ma, ANAPEC, and the normal job APIs.
    """
    resources: list[dict[str, Any]] = []
    data = _get_json(OPEN_DATA_PACKAGE_SEARCH_URL)
    if not data or not data.get("success"):
        return resources

    result = data.get("result", {})
    packages = result.get("results", []) if isinstance(result, dict) else []
    for package in packages:
        if not isinstance(package, dict):
            continue
        package_title = _clean_text(package.get("title") or package.get("name") or "Open data package")
        for item in package.get("resources", []) or []:
            if not isinstance(item, dict):
                continue
            resources.append(
                {
                    "source": "data.gov.ma",
                    "package_id": str(package.get("id", "")),
                    "package_title": package_title,
                    "id": str(item.get("id", "")),
                    "name": _clean_text(item.get("name") or item.get("description") or package_title),
                    "format": str(item.get("format", "")).upper(),
                    "url": str(item.get("url", "")),
                    "last_modified": str(item.get("last_modified") or item.get("created") or ""),
                }
            )
    LOGGER.info("data.gov.ma open data resources discovered: %d", len(resources))
    return resources


def _first_link(element: Tag, base_url: str) -> str:
    link = element.find("a", href=True)
    return urljoin(base_url, link["href"]) if link else base_url


def _all_links(element: Tag, base_url: str) -> list[str]:
    links = []
    for link in element.find_all("a", href=True):
        absolute = urljoin(base_url, link["href"])
        if absolute not in links:
            links.append(absolute)
    return links


def _extract_number(text: str) -> str:
    patterns = [
        r"(\d+)\s*(?:poste|postes|منصب|مناصب)",
        r"(?:poste|postes|منصب|مناصب)\s*:?\s*(\d+)",
        r"\((\d+)\)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1)
    return ""


def _extract_date_near(text: str, labels: list[str]) -> str:
    month_names = (
        "janvier|février|fevrier|mars|avril|mai|juin|juillet|août|aout|"
        "septembre|octobre|novembre|décembre|decembre|يناير|فبراير|مارس|"
        "أبريل|ابريل|ماي|يونيو|يوليوز|غشت|شتنبر|أكتوبر|اكتوبر|نونبر|دجنبر"
    )
    date_pattern = (
        r"(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|"
        r"\d{4}[/-]\d{1,2}[/-]\d{1,2}|"
        rf"\d{{1,2}}\s+(?:{month_names})\s+\d{{4}}(?:\s*-\s*\d{{1,2}}:\d{{2}})?)"
    )
    for label in labels:
        match = re.search(label + r".{0,80}?" + date_pattern, text, re.IGNORECASE)
        if match:
            return match.group(1)
        loose_match = re.search(label + r"\s*:?\s*([^|،,\n]{3,45})", text, re.IGNORECASE)
        if loose_match:
            return _clean_text(loose_match.group(1))
    return ""


def _cell_texts(row: Tag) -> list[str]:
    return [_clean_text(cell.get_text(" ", strip=True)) for cell in row.find_all(["td", "th"])]


def _normalize_government_job(
    *,
    source: str,
    title: str,
    company: str,
    location: str,
    description: str,
    url: str,
    source_url: str,
    deadline: str = "",
    exam_date: str = "",
    positions: str = "",
    reference: str = "",
    category: str = "",
    agency_type: str = "government",
    job_type: str = "government",
    tags: list[str] | None = None,
    application_url: str = "",
) -> dict[str, Any]:
    title = _clean_text(title)
    company = _clean_text(company)
    description = _clean_text(description) or title
    stable_reference = reference or url or _hash_id(source, title, company, deadline)
    job_id = _hash_id(source, stable_reference, title, company, deadline)
    job_url = application_url or url or source_url

    return {
        "source": source,
        "job_id": job_id,
        "title": title,
        "company": company,
        "location": location or "Morocco",
        "description": description,
        "url": job_url,
        "published_at": "",
        "fetched_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "deadline": deadline,
        "exam_date": exam_date,
        "positions": positions,
        "job_type": job_type,
        "source_type": agency_type,
        "remote": False,
        "tags": tags or [category, "Morocco", "Official"],
        "source_page": source_url,
        "announcement_url": url,
        "application_url": application_url,
    }


def _parse_emploi_public(source: dict[str, Any], soup: BeautifulSoup) -> list[dict[str, Any]]:
    jobs: list[dict[str, Any]] = []
    source_url = source["url"]
    cards = soup.select(".card")

    for card in cards[:50]:
        text = _clean_text(card.get_text(" ", strip=True))
        if len(text) < 40:
            continue
        title_node = card.select_one(".card-title, h1, h2, h3")
        title = _clean_text(title_node.get_text(" ", strip=True)) if title_node else text[:120]
        company_node = card.select_one(".card-text")
        company = _clean_text(company_node.get_text(" ", strip=True)) if company_node else "Administration publique"
        links = _all_links(card, source_url)
        if not links and card.name == "a" and card.get("href"):
            links = [urljoin(source_url, str(card["href"]))]
        announcement_url = links[0] if links else source_url
        application_url = next((link for link in links if "depot" in link.lower() or "candidature" in link.lower()), "")

        jobs.append(
            _normalize_government_job(
                source="emploi-public",
                title=title,
                company=company,
                location="Morocco",
                description=text,
                url=announcement_url,
                source_url=source_url,
                deadline=_extract_date_near(text, ["Limite de dépôt", "Dernier délai", "Date limite", "آخر أجل"]),
                exam_date=_extract_date_near(text, ["Date du concours", "تاريخ المباراة", "تاريخ إجراء المباراة"]),
                positions=_extract_number(text),
                category=source.get("category", ""),
                tags=["Emploi Public", "Concours", "Morocco"],
                application_url=application_url,
            )
        )

    if jobs:
        return jobs

    rows = soup.select("table tr")

    for row in rows[:50]:
        cells = _cell_texts(row)
        if len(cells) < 2:
            continue
        text = " | ".join(cells)
        if len(text) < 25 or "administration" in text.lower() and "poste" in text.lower():
            continue

        links = _all_links(row, source_url)
        title = cells[0]
        company = cells[1] if len(cells) > 1 else "Administration publique"
        positions = _extract_number(text)
        deadline = _extract_date_near(text, ["dernier délai", "date limite", "آخر أجل"])
        exam_date = _extract_date_near(text, ["date du concours", "تاريخ المباراة"])
        announcement_url = links[0] if links else source_url
        application_url = next((link for link in links if "depot" in link.lower() or "candidature" in link.lower()), "")

        jobs.append(
            _normalize_government_job(
                source="emploi-public",
                title=title,
                company=company,
                location="Morocco",
                description=text,
                url=announcement_url,
                source_url=source_url,
                deadline=deadline,
                exam_date=exam_date,
                positions=positions,
                category=source.get("category", ""),
                tags=["Emploi Public", "Concours", "Morocco"],
                application_url=application_url,
            )
        )

    if jobs:
        return jobs

    # Fallback: collect visible concours links if the table structure changes.
    useful_words = ["concours", "recrutement", "مباراة", "توظيف"]
    for link in soup.find_all("a", href=True)[:80]:
        title = _clean_text(link.get_text(" ", strip=True))
        href = str(link["href"])
        visible = f"{title} {href}".lower()
        if len(title) < 20 or not any(word in visible for word in useful_words):
            continue
        url = urljoin(source_url, link["href"])
        jobs.append(
            _normalize_government_job(
                source="emploi-public",
                title=title,
                company="Administration publique",
                location="Morocco",
                description=title,
                url=url,
                source_url=source_url,
                category=source.get("category", ""),
                tags=["Emploi Public", "Concours", "Morocco"],
            )
        )
    return jobs


def _parse_anapec(source: dict[str, Any], soup: BeautifulSoup) -> list[dict[str, Any]]:
    jobs: list[dict[str, Any]] = []
    source_url = source["url"]
    selectors = [
        ".offre",
        ".job",
        ".elementor-post",
        "article",
        ".card",
        "tr",
    ]
    candidates: list[Tag] = []
    for selector in selectors:
        candidates = soup.select(selector)
        if candidates:
            break

    for item in candidates[:50]:
        text = _clean_text(item.get_text(" ", strip=True))
        if len(text) < 25:
            continue
        link = _first_link(item, source_url)
        title_node = item.find(["h1", "h2", "h3", "h4", "a"])
        title = _clean_text(title_node.get_text(" ", strip=True)) if title_node else text[:100]
        reference_match = re.search(r"(?:Référence|Reference|Ref)\s*:?\s*([A-Z0-9/_-]+)", text, re.IGNORECASE)
        reference = reference_match.group(1) if reference_match else link
        positions = _extract_number(text)
        location = ""
        city_match = re.search(r"\b(Casablanca|Rabat|Marrakech|Tanger|Tangier|Fes|Fez|Agadir|Kenitra|Oujda|Tetouan|Meknes)\b", text, re.IGNORECASE)
        if city_match:
            location = city_match.group(1)

        jobs.append(
            _normalize_government_job(
                source="anapec",
                title=title,
                company="ANAPEC",
                location=location or "Morocco",
                description=text,
                url=link,
                source_url=source_url,
                positions=positions,
                reference=reference,
                category=source.get("category", ""),
                agency_type="official_agency",
                tags=["ANAPEC", "Morocco", "Offre d'emploi"],
            )
        )
    return jobs


def _parse_collectivites(source: dict[str, Any], soup: BeautifulSoup) -> list[dict[str, Any]]:
    jobs: list[dict[str, Any]] = []
    source_url = source["url"]
    candidates = soup.select("table tr") or soup.select("article, .view-content .views-row, .card, li")

    for item in candidates[:50]:
        text = _clean_text(item.get_text(" ", strip=True))
        if len(text) < 25:
            continue
        link = _first_link(item, source_url)
        title_node = item.find(["h2", "h3", "h4", "a"])
        title = _clean_text(title_node.get_text(" ", strip=True)) if title_node else text[:120]
        company_match = re.search(r"(Commune|Province|Préfecture|Conseil|جماعة|إقليم).{0,80}", text, re.IGNORECASE)
        company = _clean_text(company_match.group(0)) if company_match else "Collectivités Territoriales"

        jobs.append(
            _normalize_government_job(
                source="collectivites-territoriales",
                title=title,
                company=company,
                location="Morocco",
                description=text,
                url=link,
                source_url=source_url,
                deadline=_extract_date_near(text, ["dernier délai", "date limite", "آخر أجل"]),
                positions=_extract_number(text),
                category=source.get("category", ""),
                tags=["Collectivités Territoriales", "Concours", "Morocco"],
            )
        )
    return jobs


def _parse_ofppt(source: dict[str, Any], soup: BeautifulSoup) -> list[dict[str, Any]]:
    jobs: list[dict[str, Any]] = []
    source_url = source["url"]
    candidates = soup.select("article") or soup.select("table tr")

    for item in candidates[:80]:
        text = _clean_text(item.get_text(" ", strip=True))
        if len(text) < 25 or "référence" not in text.lower():
            continue
        if "expirée" in text.lower() or "expiree" in text.lower():
            continue
        link = _first_link(item, source_url)
        title_node = item.find(["h1", "h2", "h3", "h4", "a"])
        title = _clean_text(title_node.get_text(" ", strip=True)) if title_node else text[:100]
        if len(title) < 5 or "ofppt" == title.lower():
            continue
        reference_match = re.search(r"R[ée]f[ée]rence\s*:?\s*([A-Z0-9 /\-]+)", text, re.IGNORECASE)
        deadline = _extract_date_near(text, ["Date d.expiration", "Dernier Délai", "Date limite", "آخر أجل"])

        jobs.append(
            _normalize_government_job(
                source="ofppt-recrutement",
                title=title,
                company="OFPPT",
                location="Morocco",
                description=text,
                url=link,
                source_url=source_url,
                deadline=deadline,
                reference=reference_match.group(1).strip() if reference_match else link,
                category=source.get("category", ""),
                agency_type="public_agency",
                tags=["OFPPT", "Recrutement", "Morocco"],
            )
        )
    return jobs


def _parse_mabourse(source: dict[str, Any], soup: BeautifulSoup) -> list[dict[str, Any]]:
    jobs: list[dict[str, Any]] = []
    source_url = source["url"]
    candidates = soup.select("article, .views-row, .card, .item, li")
    if not candidates:
        candidates = [link.parent for link in soup.find_all("a", href=True) if isinstance(link.parent, Tag)]

    useful_words = ("bourse", "bours", "candidature", "programme", "formation", "منحة", "منح", "ترشيح")
    for item in candidates[:120]:
        text = _clean_text(item.get_text(" ", strip=True))
        if len(text) < 18 or not any(word in text.lower() for word in useful_words):
            continue
        link = _first_link(item, source_url)
        title_node = item.find(["h1", "h2", "h3", "h4", "a"])
        title = _clean_text(title_node.get_text(" ", strip=True)) if title_node else text[:100]
        if len(title) < 6:
            continue

        jobs.append(
            _normalize_government_job(
                source="mabourse-enssup",
                title=title,
                company="Ministère de l'Enseignement Supérieur",
                location="Morocco",
                description=text,
                url=link,
                source_url=source_url,
                deadline=_extract_date_near(text, ["Date de clôture", "Date limite", "Délai", "آخر أجل"]),
                reference=link,
                category=source.get("category", ""),
                agency_type="scholarship",
                job_type="scholarship",
                tags=["Bourse", "Etudes", "Morocco"],
            )
        )
    return jobs


def _parse_official_links(source: dict[str, Any], soup: BeautifulSoup) -> list[dict[str, Any]]:
    jobs: list[dict[str, Any]] = []
    source_url = source["url"]
    include_keywords = [str(item).lower() for item in source.get("keywords", [])]
    if not include_keywords:
        include_keywords = [
            "recrutement",
            "offre",
            "emploi",
            "concours",
            "candidature",
            "bourse",
            "formation",
            "منحة",
            "مباراة",
            "توظيف",
            "ترشيح",
        ]

    seen: set[str] = set()
    excluded_keywords = (
        "appel d'offre",
        "appel d’offres",
        "appels d'offres",
        "appels d’offres",
        "marchés publics",
        "marches publics",
        "plan du site",
        "contact",
        "newsletter",
        "mentions légales",
    )
    for link_node in soup.find_all("a", href=True)[:180]:
        title = _clean_text(link_node.get_text(" ", strip=True))
        url = urljoin(source_url, str(link_node["href"]))
        visible = f"{title} {url}".lower()
        if any(keyword in visible for keyword in excluded_keywords):
            continue
        if len(title) < 12 or not any(keyword in visible for keyword in include_keywords):
            continue
        if url in seen:
            continue
        seen.add(url)
        text = _clean_text((link_node.parent.get_text(" ", strip=True) if isinstance(link_node.parent, Tag) else title))
        jobs.append(
            _normalize_government_job(
                source=urlparse(source_url).netloc.replace("www.", ""),
                title=title,
                company=source.get("name", "Official source"),
                location="Morocco",
                description=text or title,
                url=url,
                source_url=source_url,
                deadline=_extract_date_near(text, ["Date limite", "Dernier délai", "Date d.expiration", "آخر أجل"]),
                reference=url,
                category=source.get("category", ""),
                agency_type=source.get("type", "government"),
                job_type="scholarship" if "bourse" in visible or "منح" in visible or "منحة" in visible else "government",
                tags=[source.get("name", "Official"), "Morocco"],
            )
        )
    return jobs


def _parse_generic_official_source(source: dict[str, Any], soup: BeautifulSoup) -> list[dict[str, Any]]:
    jobs: list[dict[str, Any]] = []
    source_url = source["url"]
    for link in soup.find_all("a", href=True)[:80]:
        title = _clean_text(link.get_text(" ", strip=True))
        if len(title) < 20:
            continue
        url = urljoin(source_url, link["href"])
        jobs.append(
            _normalize_government_job(
                source=urlparse(source_url).netloc.replace("www.", ""),
                title=title,
                company=source.get("name", "Official source"),
                location="Morocco",
                description=title,
                url=url,
                source_url=source_url,
                category=source.get("category", ""),
                agency_type=source.get("type", "government"),
                tags=[source.get("name", "Official"), "Morocco"],
            )
        )
    return jobs


def _parse_source(source: dict[str, Any], soup: BeautifulSoup) -> list[dict[str, Any]]:
    host = urlparse(source["url"]).netloc.lower()
    parser = str(source.get("parser", "")).lower()
    if parser == "ofppt":
        return _parse_ofppt(source, soup)
    if parser == "mabourse":
        return _parse_mabourse(source, soup)
    if parser == "official_links":
        return _parse_official_links(source, soup)
    if "emploi-public.ma" in host:
        return _parse_emploi_public(source, soup)
    if "anapec.ma" in host:
        return _parse_anapec(source, soup)
    if "recrutement.ofppt.ma" in host or "ofppt.ma" in host:
        return _parse_ofppt(source, soup)
    if "mabourse.enssup.gov.ma" in host:
        return _parse_mabourse(source, soup)
    if "collectivites-territoriales.gov.ma" in host:
        return _parse_collectivites(source, soup)
    if source.get("type") in {"scholarship", "official_agency", "government"}:
        official_jobs = _parse_official_links(source, soup)
        if official_jobs:
            return official_jobs
    return _parse_generic_official_source(source, soup)


def fetch_government_jobs() -> list[dict[str, Any]]:
    max_items_per_source = max(1, int(os.getenv("GOV_MAX_ITEMS_PER_SOURCE", "20")))
    sources = _load_sources()
    LOGGER.info("Government sources checked: %d configured source(s).", len(sources))

    jobs: list[dict[str, Any]] = []
    for source in sources:
        if source.get("type") == "open_data":
            fetch_open_data_resources()
            continue
        soup = _get_soup(source["url"])
        if soup is None:
            continue
        source_jobs = _parse_source(source, soup)[:max_items_per_source]
        LOGGER.info("Government source %s fetched %d job(s).", source.get("name"), len(source_jobs))
        jobs.extend(source_jobs)

    LOGGER.info("Government jobs fetched: %d", len(jobs))
    return jobs
