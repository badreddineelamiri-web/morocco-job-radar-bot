"""OFPPT scraper."""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

from scrapers.base import BaseScraper


class OfpptScraper(BaseScraper):
    def parse(self, soup: BeautifulSoup) -> list[dict]:
        jobs: list[dict] = []
        for item in self.generic_cards(soup)[:100]:
            text = self.clean_text(item.get_text(" ", strip=True))
            if len(text) < 20:
                continue
            visible = text.lower()
            if "expir" in visible:
                continue
            if not any(word in visible for word in ("référence", "reference", "recrutement", "offre", "emploi")):
                continue
            title = self.title_from(item, text[:120])
            normalized_title = title.lower().replace("é", "e").replace("Ã©", "e")
            if normalized_title.startswith("reference poste dernier delai"):
                continue
            jobs.append(
                self.normalize_job(
                    title=title,
                    organization="OFPPT",
                    city=self._city(text),
                    description=text,
                    url=self.first_link(item),
                    deadline=self.extract_labeled_date(text, ["Date d'expiration", "Dernier délai", "Date limite"]),
                    reference=self._reference(text),
                    pdf_url=self.pdf_link(item),
                )
            )
        return jobs

    def _reference(self, text: str) -> str:
        match = re.search(r"R[ée]f[ée]rence\s*:?\s*([A-Z0-9/_ -]+)", text, re.IGNORECASE)
        return self.clean_text(match.group(1)) if match else ""

    def _city(self, text: str) -> str:
        match = re.search(r"(Casablanca|Rabat|Marrakech|Tanger|Fès|Fes|Agadir|Oujda|Meknes|Safi)", text, re.IGNORECASE)
        return match.group(1) if match else ""
