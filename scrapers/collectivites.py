"""Collectivites territoriales scraper."""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

from scrapers.base import BaseScraper


class CollectivitesScraper(BaseScraper):
    def parse(self, soup: BeautifulSoup) -> list[dict]:
        jobs: list[dict] = []
        for item in self.generic_cards(soup)[:80]:
            text = self.clean_text(item.get_text(" ", strip=True))
            if len(text) < 25:
                continue
            jobs.append(
                self.normalize_job(
                    title=self.title_from(item, text[:130]),
                    organization=self._collectivity(text),
                    description=text,
                    url=self.first_link(item),
                    deadline=self.extract_labeled_date(text, ["Dernier délai", "Date limite", "آخر أجل"]),
                    exam_date=self.extract_labeled_date(text, ["Date du concours", "تاريخ المباراة"]),
                    positions_count=self.extract_number(text),
                    pdf_url=self.pdf_link(item),
                )
            )
        return jobs

    def _collectivity(self, text: str) -> str:
        match = re.search(r"(Commune|Province|Préfecture|Prefecture|Région|Region|جماعة|إقليم|عمالة|جهة).{0,90}", text, re.IGNORECASE)
        return self.clean_text(match.group(0)) if match else "Collectivites Territoriales"
