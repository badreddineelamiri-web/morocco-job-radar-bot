"""ANAPEC scraper."""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

from scrapers.base import BaseScraper


class AnapecScraper(BaseScraper):
    def parse(self, soup: BeautifulSoup) -> list[dict]:
        jobs: list[dict] = []
        candidates = soup.select(".offre, .job, article, .card, .elementor-post, table tr, li")
        for item in candidates[:80]:
            text = self.clean_text(item.get_text(" ", strip=True))
            if len(text) < 25:
                continue
            title = self.title_from(item, text[:120])
            if len(title) < 5:
                continue
            jobs.append(
                self.normalize_job(
                    title=title,
                    company=self._company(text),
                    city=self._city(text),
                    description=text,
                    url=self.first_link(item),
                    publication_date=self.extract_labeled_date(text, ["Date", "Publié", "Publication"]),
                    positions_count=self.extract_number(text),
                    application_method=self._application_method(text),
                )
            )
        return jobs

    def _city(self, text: str) -> str:
        cities = "Casablanca|Casa-Nouacer|Rabat|Marrakech|Tanger|Fès|Fes|Agadir|Kenitra|Oujda|Tetouan|Meknes|Safi|El Jadida|Essaouira|Sale|Salé|Nador"
        match = re.search(rf"\b({cities})\b", text, re.IGNORECASE)
        return match.group(1) if match else ""

    def _company(self, text: str) -> str:
        match = re.search(r"(?:Entreprise|Société|Employeur)\s*:?\s*([^|,\n]{3,80})", text, re.IGNORECASE)
        return self.clean_text(match.group(1)) if match else "ANAPEC"

    def _application_method(self, text: str) -> str:
        match = re.search(r"(?:Postuler|Candidature|Envoyer|Email|E-mail).{0,120}", text, re.IGNORECASE)
        return self.clean_text(match.group(0)) if match else ""
