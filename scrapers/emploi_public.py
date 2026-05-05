"""Emploi Public scraper."""

from __future__ import annotations

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
                    organization=self._organization(text),
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

    def _organization(self, text: str) -> str:
        markers = ["Administration organisatrice", "Administration", "الإدارة المنظمة"]
        for marker in markers:
            if marker.lower() in text.lower():
                return text.split(marker, 1)[-1].strip(" :|-")[:140]
        return "Administration publique"
