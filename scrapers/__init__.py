"""Scraper registry."""

from __future__ import annotations

from typing import Any

from scrapers.anapec import AnapecScraper
from scrapers.collectivites import CollectivitesScraper
from scrapers.emploi_ma import EmploiMaScraper
from scrapers.emploi_public import EmploiPublicScraper
from scrapers.enssup import EnssupScraper
from scrapers.marocannonces import MarocAnnoncesScraper
from scrapers.ministry_generic import MinistryGenericScraper
from scrapers.ofppt import OfpptScraper


SCRAPERS = {
    "emploi_public": EmploiPublicScraper,
    "anapec": AnapecScraper,
    "enssup": EnssupScraper,
    "collectivites": CollectivitesScraper,
    "ofppt": OfpptScraper,
    "ministry_generic": MinistryGenericScraper,
    "emploi_ma": EmploiMaScraper,
    "marocannonces": MarocAnnoncesScraper,
}


def scraper_for(source: dict[str, Any]):
    scraper_name = str(source.get("scraper") or "ministry_generic")
    scraper_class = SCRAPERS.get(scraper_name, MinistryGenericScraper)
    return scraper_class(source)
