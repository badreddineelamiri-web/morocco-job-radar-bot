"""Fast job scraping using Scrapling for rapid job discovery."""

from __future__ import annotations

import logging
import re
from typing import Any
from urllib.parse import urljoin, urlparse

from scrapling.fetchers import Fetcher
from scrapling.parser import Selector


LOGGER = logging.getLogger(__name__)


def _extract_job_links(page: Selector, base_url: str) -> list[str]:
    """Extract job links from a page using common selectors."""
    links = set()
    
    # Common selectors for job links
    selectors = [
        'a[href*="job"]', 'a[href*="emploi"]', 'a[href*="offre"]',
        'a[href*="concours"]', 'a[href*="recrutement"]',
        '.job-link', '.job-item a', '.offre a', '.job-title a',
        'h2 a', 'h3 a', '.title a', 'article a'
    ]
    
    for selector in selectors:
        try:
            elements = page.css(selector)
            for elem in elements:
                href = elem.attrib.get('href') if hasattr(elem, 'attrib') else elem.get('href')
                if href:
                    full_url = urljoin(base_url, href)
                    if _is_job_url(full_url):
                        links.add(full_url)
        except Exception as e:
            LOGGER.debug(f"Selector {selector} failed: {e}")
            continue
    
    return list(links)


def _is_job_url(url: str) -> bool:
    """Check if URL likely contains job information."""
    job_keywords = [
        'job', 'emploi', 'offre', 'concours', 'recrutement',
        'poste', 'position', 'career', 'vacancy', 'announce'
    ]
    url_lower = url.lower()
    return any(keyword in url_lower for keyword in job_keywords)


def _extract_job_details(page: Selector, url: str) -> dict[str, Any] | None:
    """Extract job details from a page."""
    try:
        # Try to get structured data first
        job_data = {}
        
        # Title
        title_selectors = ['h1', 'h2.job-title', '.job-title', '.title', 'header h1']
        for sel in title_selectors:
            elem = page.css_first(sel)
            if elem:
                title = elem.text(strip=True)
                if title and len(title) > 5:
                    job_data['title'] = title
                    break
        
        # Company
        company_selectors = ['.company', '.employer', '.organization', '[itemprop="hiringOrganization"]']
        for sel in company_selectors:
            elem = page.css_first(sel)
            if elem:
                company = elem.text(strip=True)
                if company:
                    job_data['company'] = company
                    break
        
        # Location
        location_selectors = ['.location', '.city', '[itemprop="jobLocation"]', '.place']
        for sel in location_selectors:
            elem = page.css_first(sel)
            if elem:
                location = elem.text(strip=True)
                if location:
                    job_data['location'] = location
                    break
        
        # Description
        desc_selectors = ['.description', '.content', 'article', '.details', '[itemprop="description"]']
        for sel in desc_selectors:
            elem = page.css_first(sel)
            if elem:
                desc = elem.text(strip=True)
                if desc and len(desc) > 50:
                    job_data['description'] = desc[:500]
                    break
        
        # Application URL
        job_data['application_url'] = url
        
        # Source
        parsed = urlparse(url)
        job_data['source'] = f"{parsed.scheme}://{parsed.netloc}"
        
        # Default values
        job_data.setdefault('title', 'وظيفة جديدة')
        job_data.setdefault('company', 'شركة/مؤسسة')
        job_data.setdefault('location', 'المغرب')
        job_data.setdefault('job_type', 'private')
        
        return job_data if job_data.get('title') else None
        
    except Exception as e:
        LOGGER.error(f"Error extracting job details from {url}: {e}")
        return None


def scrape_jobs_fast(source_url: str, max_jobs: int = 5) -> list[dict[str, Any]]:
    """Scrape jobs quickly using Scrapling.
    
    Args:
        source_url: URL to scrape for jobs
        max_jobs: Maximum number of jobs to return
        
    Returns:
        List of job dictionaries
    """
    jobs = []
    
    try:
        LOGGER.info(f"Fast scraping jobs from: {source_url}")
        
        # Fetch the page using Fetcher
        fetcher = Fetcher()
        response = fetcher.get(source_url, timeout=15)
        if response is None or not getattr(response, "text", ""):
            LOGGER.error(f"Failed to fetch {source_url}")
            return jobs
        
        # Parse with Selector
        page = Selector(response.text, source_url)
        
        # Extract job links
        job_links = _extract_job_links(page, source_url)
        LOGGER.info(f"Found {len(job_links)} potential job links")
        
        # Limit number of jobs to process
        job_links = job_links[:max_jobs * 2]  # Get more to account for failures
        
        # Extract details from each link
        for link in job_links:
            if len(jobs) >= max_jobs:
                break
            
            try:
                job_response = fetcher.get(link, timeout=10)
                if job_response is not None and getattr(job_response, "text", ""):
                    job_page = Selector(job_response.text, link)
                    job_data = _extract_job_details(job_page, link)
                    if job_data:
                        jobs.append(job_data)
                        LOGGER.info(f"Scraped job: {job_data['title']}")
            except Exception as e:
                LOGGER.debug(f"Failed to scrape job from {link}: {e}")
                continue
        
        LOGGER.info(f"Successfully scraped {len(jobs)} jobs from {source_url}")
        
    except Exception as e:
        LOGGER.error(f"Error during fast scraping from {source_url}: {e}")
    
    return jobs


def scrape_multiple_sources(sources: list[dict[str, Any]], max_per_source: int = 3) -> list[dict[str, Any]]:
    """Scrape jobs from multiple sources.
    
    Args:
        sources: List of source dictionaries with 'url' key
        max_per_source: Max jobs per source
        
    Returns:
        Combined list of jobs
    """
    all_jobs = []
    
    for source in sources:
        url = source.get('url')
        if not url:
            continue
        
        jobs = scrape_jobs_fast(url, max_jobs=max_per_source)
        all_jobs.extend(jobs)
    
    return all_jobs
