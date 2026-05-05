"""Generic official ministry scraper."""

from __future__ import annotations

from bs4 import BeautifulSoup

from scrapers.base import BaseScraper


class MinistryGenericScraper(BaseScraper):
    def parse(self, soup: BeautifulSoup) -> list[dict]:
        jobs: list[dict] = []
        keywords = (
            "recrutement",
            "concours",
            "emploi",
            "candidature",
            "poste de responsabilité",
            "postes de responsabilite",
            "مباراة",
            "توظيف",
            "ترشيح",
        )
        seen: set[str] = set()
        for link in soup.find_all("a", href=True)[:220]:
            title = self.clean_text(link.get_text(" ", strip=True))
            url = self.absolute_url(str(link["href"]))
            visible = f"{title} {url}".lower()
            if len(title) < 8 or not any(keyword in visible for keyword in keywords):
                continue
            if url in seen:
                continue
            seen.add(url)
            parent_text = self.clean_text(link.parent.get_text(" ", strip=True) if link.parent else title)
            jobs.append(
                self.normalize_job(
                    title=title,
                    organization=self.source["name"],
                    description=parent_text or title,
                    url=url,
                    deadline=self.extract_labeled_date(parent_text, ["Dernier délai", "Date limite", "آخر أجل"]),
                    publication_date=self.extract_labeled_date(parent_text, ["Date de publication", "Publié", "نشر"]),
                    pdf_url=url if ".pdf" in url.lower() else "",
                )
            )
        return jobs
