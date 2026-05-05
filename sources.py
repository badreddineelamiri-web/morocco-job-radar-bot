"""Configured Moroccan job sources for round-robin scraping."""

from __future__ import annotations

from typing import Any


SOURCES: list[dict[str, Any]] = [
    {
        "name": "Emploi Public",
        "url": "https://www.emploi-public.ma/fr/concours-liste",
        "type": "official_public",
        "priority": 100,
        "category": "concours_publics",
        "enabled": True,
        "scraper": "emploi_public",
    },
    {
        "name": "ANAPEC",
        "url": "https://anapec.ma/home-page-o1/chercheur-emploi/offres-demploi/",
        "type": "official_jobs",
        "priority": 90,
        "category": "private_jobs",
        "enabled": True,
        "scraper": "anapec",
        "timeout": 25,
        "retries": 2,
    },
    {
        "name": "Enseignement Superieur Recrutement",
        "url": "https://recrutement.enssup.gov.ma/annonce/",
        "type": "official_public",
        "priority": 85,
        "category": "education_jobs",
        "enabled": True,
        "scraper": "enssup",
    },
    {
        "name": "Collectivites Territoriales",
        "url": "https://www.collectivites-territoriales.gov.ma/fr/recrutement/concours",
        "type": "official_public",
        "priority": 85,
        "category": "local_government",
        "enabled": True,
        "scraper": "collectivites",
    },
    {
        "name": "OFPPT",
        "url": "https://www.ofppt.ma/index.php/fr/offres-d-emploi",
        "type": "public_institution",
        "priority": 80,
        "category": "public_institution",
        "enabled": True,
        "scraper": "ofppt",
    },
    {
        "name": "Ministere Industrie Commerce",
        "url": "https://www.mcinet.gov.ma/fr/emplois-et-candidatures-aux-postes-de-responsabilite",
        "type": "official_ministry",
        "priority": 75,
        "category": "ministry_jobs",
        "enabled": True,
        "scraper": "ministry_generic",
    },
    {
        "name": "Ministere Equipement Eau",
        "url": "https://www.equipement.gov.ma/Formation/Recrutement/Pages/Concours-de-recrutement.aspx",
        "type": "official_ministry",
        "priority": 75,
        "category": "ministry_jobs",
        "enabled": True,
        "scraper": "ministry_generic",
    },
    {
        "name": "Ministere Transport Logistique",
        "url": "https://www.transport.gov.ma/fr/recrutement-et-carrieres",
        "type": "official_ministry",
        "priority": 75,
        "category": "ministry_jobs",
        "enabled": True,
        "scraper": "ministry_generic",
    },
    {
        "name": "Ministere Habitat Urbanisme",
        "url": "https://www.mhpv.gov.ma/fr/concours/",
        "type": "official_ministry",
        "priority": 75,
        "category": "ministry_jobs",
        "enabled": True,
        "scraper": "ministry_generic",
    },
    {
        "name": "Emploi.ma",
        "url": "https://www.emploi.ma/recherche-jobs-maroc",
        "type": "private_jobboard",
        "priority": 60,
        "category": "private_jobs",
        "enabled": True,
        "scraper": "emploi_ma",
    },
    {
        "name": "MarocAnnonces Emploi",
        "url": "https://www.marocannonces.com/emploi",
        "type": "private_classifieds",
        "priority": 40,
        "category": "private_jobs",
        "enabled": True,
        "scraper": "marocannonces",
    },
]


def enabled_sources() -> list[dict[str, Any]]:
    """Return enabled sources in priority order."""
    return sorted(
        [source for source in SOURCES if source.get("enabled", True)],
        key=lambda source: int(source.get("priority", 0)),
        reverse=True,
    )
