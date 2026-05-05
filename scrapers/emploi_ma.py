"""Emploi.ma scraper."""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

from scrapers.base import BaseScraper


class EmploiMaScraper(BaseScraper):
    def parse(self, soup: BeautifulSoup) -> list[dict]:
        jobs: list[dict] = []
        candidates = soup.select(".job-description-wrapper, .search-description, article, .card, .views-row")
        for item in candidates[:80]:
            text = self.clean_text(item.get_text(" ", strip=True))
            if len(text) < 35:
                continue
            title = self.title_from(item, text[:100])
            jobs.append(
                self.normalize_job(
                    title=title,
                    company=self._company(text),
                    city=self._city(text),
                    description=text,
                    url=self.first_link(item),
                    publication_date=self.extract_labeled_date(text, ["Publiée", "Publiée le", "Date", "Publié"]),
                    positions_count=self.extract_number(text),
                    application_method="Voir le lien de l'offre",
                )
            )
        return jobs

    def _company(self, text: str) -> str:
        match = re.search(r"(?:Entreprise|Société|Recruteur)\s*:?\s*([^|,\n]{3,80})", text, re.IGNORECASE)
        return self.clean_text(match.group(1)) if match else "Emploi.ma"

    def _city(self, text: str) -> str:
        match = re.search(r"(Casablanca|Rabat|Marrakech|Tanger|Fès|Fes|Agadir|Oujda|Meknes|Safi|Kenitra)", text, re.IGNORECASE)
        return match.group(1) if match else ""
