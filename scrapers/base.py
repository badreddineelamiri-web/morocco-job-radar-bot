"""Base scraper helpers for respectful HTML fetching."""

from __future__ import annotations

import datetime as dt
import hashlib
import logging
import os
import random
import re
import time
from typing import Any
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup, Tag

from date_parser import extract_date_text


LOGGER = logging.getLogger(__name__)
DEFAULT_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "20"))


class BaseScraper:
    """Base class for one source scraper."""

    def __init__(self, source: dict[str, Any]) -> None:
        self.source = source
        self.url = str(source["url"])
        self.timeout = int(source.get("timeout") or DEFAULT_TIMEOUT)
        self.retries = int(source.get("retries") or 1)
        self.session = requests.Session()
        self.headers = {
            "User-Agent": "Mozilla/5.0 (compatible; MoroccoJobRadarBot/1.0; +https://github.com/badreddineelamiri-web/morocco-job-radar-bot)",
            "Accept-Language": "ar,fr;q=0.9,en;q=0.8",
        }

    def fetch(self, url: str | None = None) -> BeautifulSoup:
        target = url or self.url
        last_error: Exception | None = None
        for attempt in range(self.retries + 1):
            if attempt:
                time.sleep(random.uniform(1, 3))
            try:
                response = self.session.get(target, headers=self.headers, timeout=self.timeout)
                response.raise_for_status()
                if not response.encoding:
                    response.encoding = response.apparent_encoding
                return BeautifulSoup(response.text, "html.parser")
            except requests.RequestException as exc:
                last_error = exc
        raise RuntimeError(f"{target} failed after {self.retries + 1} request(s): {last_error}")

    def scrape(self) -> list[dict[str, Any]]:
        time.sleep(random.uniform(1, 3))
        return self.parse(self.fetch())

    def parse(self, soup: BeautifulSoup) -> list[dict[str, Any]]:
        raise NotImplementedError

    def clean_text(self, value: Any) -> str:
        return re.sub(r"\s+", " ", str(value or "")).strip()

    def absolute_url(self, href: str | None) -> str:
        return urljoin(self.url, href or "")

    def first_link(self, element: Tag) -> str:
        link = element.find("a", href=True)
        return self.absolute_url(str(link["href"])) if link else self.url

    def pdf_link(self, element: Tag) -> str:
        for link in element.find_all("a", href=True):
            url = self.absolute_url(str(link["href"]))
            if ".pdf" in url.lower():
                return url
        return ""

    def title_from(self, element: Tag, fallback: str = "") -> str:
        node = element.find(["h1", "h2", "h3", "h4", "a"])
        return self.clean_text(node.get_text(" ", strip=True) if node else fallback)

    def extract_number(self, text: str) -> str:
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

    def extract_labeled_date(self, text: str, labels: list[str]) -> str:
        for label in labels:
            match = re.search(label + r".{0,90}", text, re.IGNORECASE)
            if match:
                found = extract_date_text(match.group(0))
                if found:
                    return found
        return extract_date_text(text)

    def normalize_job(
        self,
        *,
        title: str,
        organization: str = "",
        company: str = "",
        city: str = "",
        description: str = "",
        url: str = "",
        deadline: str = "",
        exam_date: str = "",
        publication_date: str = "",
        positions_count: str = "",
        pdf_url: str = "",
        reference: str = "",
        application_method: str = "",
        specialty: str = "",
    ) -> dict[str, Any]:
        official = str(self.source.get("type", "")) in {
            "official_public",
            "official_ministry",
            "public_institution",
        }
        job_type = "government" if official and self.source.get("category") != "private_jobs" else "private"
        link = url or pdf_url or self.url
        title = self.clean_text(title)
        organization = self.clean_text(organization or company)
        raw_id = "|".join([link, title, organization])
        job_id = hashlib.sha256(raw_id.lower().encode("utf-8")).hexdigest()[:20]
        return {
            "id": job_id,
            "job_id": job_id,
            "title": title,
            "job_title": title,
            "organization": organization,
            "company": organization or self.source["name"],
            "city": self.clean_text(city),
            "location": self.clean_text(city) or "Morocco",
            "description": self.clean_text(description or title),
            "url": link,
            "announcement_url": link,
            "application_url": link,
            "pdf_url": pdf_url,
            "official_url": link,
            "source": self.source["name"],
            "source_name": self.source["name"],
            "source_type": self.source["type"],
            "source_category": self.source["category"],
            "source_page": self.url,
            "job_type": job_type,
            "deadline": self.clean_text(deadline),
            "exam_date": self.clean_text(exam_date),
            "publication_date": self.clean_text(publication_date),
            "published_at": self.clean_text(publication_date),
            "positions_count": self.clean_text(positions_count),
            "positions": self.clean_text(positions_count),
            "reference": self.clean_text(reference),
            "application_method": self.clean_text(application_method),
            "specialty": self.clean_text(specialty),
            "fetched_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        }

    def generic_cards(self, soup: BeautifulSoup) -> list[Tag]:
        selectors = ["article", ".views-row", ".card", ".item", ".offre", ".job", "tr", "li"]
        for selector in selectors:
            items = soup.select(selector)
            if items:
                return [item for item in items if isinstance(item, Tag)]
        return []
