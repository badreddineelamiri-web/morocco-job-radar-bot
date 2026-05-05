"""Higher education recruitment scraper."""

from __future__ import annotations

from bs4 import BeautifulSoup

from scrapers.base import BaseScraper


class EnssupScraper(BaseScraper):
    def parse(self, soup: BeautifulSoup) -> list[dict]:
        jobs: list[dict] = []
        for item in self.generic_cards(soup)[:80]:
            text = self.clean_text(item.get_text(" ", strip=True))
            if len(text) < 25:
                continue
            title = self.title_from(item, text[:120])
            jobs.append(
                self.normalize_job(
                    title=title,
                    organization=self._institution(text),
                    description=text,
                    url=self.first_link(item),
                    deadline=self.extract_labeled_date(text, ["Dernier délai", "Date limite", "آخر أجل"]),
                    publication_date=self.extract_labeled_date(text, ["Date de publication", "Publication", "نشر"]),
                    pdf_url=self.pdf_link(item),
                    specialty=self._specialty(text),
                )
            )
        return jobs

    def _institution(self, text: str) -> str:
        for word in ("Université", "Faculté", "Ecole", "École", "Institut", "جامعة", "كلية", "معهد"):
            if word.lower() in text.lower():
                start = text.lower().find(word.lower())
                return text[start : start + 120]
        return "Enseignement Superieur"

    def _specialty(self, text: str) -> str:
        for label in ("Spécialité", "Specialite", "التخصص"):
            if label.lower() in text.lower():
                return text.split(label, 1)[-1].strip(" :|-")[:100]
        return ""
