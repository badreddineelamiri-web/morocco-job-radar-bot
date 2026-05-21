"""Emploi Public scraper."""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

from scrapers.base import BaseScraper


class EmploiPublicScraper(BaseScraper):
    def parse(self, soup: BeautifulSoup) -> list[dict]:
        jobs: list[dict] = []
        candidates = soup.select(".card, table tr, article, .views-row")
        if not candidates:
            candidates = [link.parent for link in soup.find_all("a", href=True) if link.parent]

        for item in candidates[:80]:
            text = self.clean_text(item.get_text(" ", strip=True))
            if len(text) < 25:
                continue
            title = self.title_from(item, text[:140])
            if len(title) < 8:
                continue
            url = self.first_link(item)
            pdf_url = self.pdf_link(item)
            jobs.append(
                self.normalize_job(
                    title=title,
                    organization=self._organization(text, title),
                    description=text,
                    url=url,
                    deadline=self.extract_labeled_date(
                        text,
                        ["Limite de dépôt", "Limite de depot", "Dernier délai", "Date limite", "آخر أجل"],
                    ),
                    exam_date=self.extract_labeled_date(text, ["Date du concours", "تاريخ المباراة"]),
                    positions_count=self.extract_number(text),
                    pdf_url=pdf_url,
                )
            )
        return jobs

    def _organization(self, text: str, title: str = "") -> str:
        markers = ["Administration organisatrice", "Administration", "الإدارة المنظمة"]
        for marker in markers:
            if marker.lower() in text.lower():
                return text.split(marker, 1)[-1].strip(" :|-")[:140]
        remainder = text
        if title and remainder.lower().startswith(title.lower()):
            remainder = remainder[len(title) :].strip()
        remainder = re.split(
            r"\b(?:Annonce|Dépôt|Depot|Arrêté|Arrete|Limite de dépôt|Limite de depot|\d+\s+postes?)\b",
            remainder,
            maxsplit=1,
            flags=re.IGNORECASE,
        )[0]
        remainder = self.clean_text(remainder).strip(" :|-")
        if len(remainder) >= 4:
            return remainder[:140]
        return "Administration publique"
