"""MarocAnnonces employment scraper."""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

from scrapers.base import BaseScraper


class MarocAnnoncesScraper(BaseScraper):
    def parse(self, soup: BeautifulSoup) -> list[dict]:
        jobs: list[dict] = []
        candidates = soup.select(".cars-list li, .listing li, article, .card, li")
        for item in candidates[:100]:
            text = self.clean_text(item.get_text(" ", strip=True))
            if len(text) < 30:
                continue
            title = self.title_from(item, text[:100])
            jobs.append(
                self.normalize_job(
                    title=title,
                    company="MarocAnnonces",
                    city=self._city(text),
                    description=text,
                    url=self.first_link(item),
                    publication_date=self.extract_labeled_date(text, ["Date", "Publié", "Annonce"]),
                    application_method=self._application_method(text),
                )
            )
        return jobs

    def _city(self, text: str) -> str:
        match = re.search(r"(Casablanca|Rabat|Marrakech|Tanger|Fès|Fes|Agadir|Oujda|Meknes|Safi|Kenitra|Tetouan|Nador)", text, re.IGNORECASE)
        return match.group(1) if match else ""

    def _application_method(self, text: str) -> str:
        if re.search(r"email|e-mail|gmail|@|postuler|candidature|téléphone|telephone|whatsapp", text, re.IGNORECASE):
            return "Coordonnées indiquées dans l'annonce"
        return ""
