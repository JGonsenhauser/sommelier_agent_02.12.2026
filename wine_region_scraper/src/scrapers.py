"""
Scraper modules for wine taxonomy data from various sources.
"""
import requests
from bs4 import BeautifulSoup
from typing import List, Dict
from urllib.parse import urljoin
import time
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


def get_session_with_retries(retries=3, backoff_factor=0.5):
    """Create requests session with retry strategy."""
    session = requests.Session()
    retry_strategy = Retry(
        total=retries,
        backoff_factor=backoff_factor,
        status_forcelist=[429, 500, 502, 503, 504],
        method_whitelist=["HEAD", "GET", "OPTIONS"]
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


def scrape_wine_folly(region_name: str) -> Dict:
    """
    Scrape Wine Folly for region information.
    Target: https://winefolly.com/update/wine-regions/
    """
    base_url = "https://winefolly.com/update/wine-regions/"
    session = get_session_with_retries()
    
    try:
        response = session.get(base_url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Parse region data
        # Note: Actual parsing depends on Wine Folly's current HTML structure
        return {"source": "wine_folly", "region": region_name}
    except Exception as e:
        print(f"Error scraping Wine Folly: {e}")
        return None


def scrape_wine_searcher_regions() -> List[Dict]:
    """
    Scrape Wine-Searcher region pages.
    Target: https://www.wine-searcher.com/regions/
    """
    base_url = "https://www.wine-searcher.com/regions/"
    session = get_session_with_retries()
    
    try:
        response = session.get(base_url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Parse region listings
        # Note: Actual parsing depends on Wine-Searcher's current HTML structure
        return []
    except Exception as e:
        print(f"Error scraping Wine-Searcher: {e}")
        return []


# Manual curation sources (non-scraped)
MANUAL_CURATION_SOURCES = {
    "jancis_robinson": "https://www.jancisrobinson.com/",
    "guildsomm": "https://www.guildsomm.com/",
    "oxford_companion": "Oxford Companion to Wine (print/reference)"
}
