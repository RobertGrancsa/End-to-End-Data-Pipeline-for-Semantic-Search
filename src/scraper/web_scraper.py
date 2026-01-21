"""
Web Scraper Module

A scalable web scraper for data aggregation that fetches HTML content,
cleans it, and extracts raw text for further processing.

Author: Rares-Alexandru Constantin
Essay: "Developing a Scalable Web Scraper for Data Aggregation"
"""

import time
import hashlib
from typing import List, Dict, Optional, Generator, Set
from urllib.parse import urljoin, urlparse
from dataclasses import dataclass, field
from datetime import datetime
import requests
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.config import config


@dataclass
class ScrapedDocument:
    """Represents a scraped web document"""
    url: str
    title: str
    content: str
    timestamp: str
    domain: str
    doc_id: str
    metadata: Dict = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization"""
        return {
            "doc_id": self.doc_id,
            "url": self.url,
            "title": self.title,
            "content": self.content,
            "timestamp": self.timestamp,
            "domain": self.domain,
            "metadata": self.metadata
        }


class WebScraper:
    """
    A scalable web scraper that crawls websites and extracts content.
    
    Features:
    - Respects rate limiting with configurable delays
    - Handles retries with exponential backoff
    - Extracts clean text from HTML
    - Generates unique document IDs
    - Supports multiple user agents for rotation
    """
    
    def __init__(
        self,
        delay_seconds: float = None,
        max_pages: int = None,
        user_agent: str = None
    ):
        """
        Initialize the web scraper.
        
        Args:
            delay_seconds: Delay between requests (default from config)
            max_pages: Maximum pages to scrape per site (default from config)
            user_agent: Custom user agent string (optional)
        """
        self.delay_seconds = delay_seconds or config.scraper.delay_seconds
        self.max_pages = max_pages or config.scraper.max_pages_per_site
        self.user_agent = user_agent or config.scraper.user_agent
        
        # Initialize fake user agent for rotation
        try:
            self.ua = UserAgent()
        except:
            self.ua = None
            
        self.session = requests.Session()
        self.visited_urls: Set[str] = set()
        
        logger.info(f"WebScraper initialized with delay={self.delay_seconds}s, max_pages={self.max_pages}")
    
    def _get_headers(self) -> Dict[str, str]:
        """Generate request headers with rotating user agent"""
        ua = self.ua.random if self.ua else self.user_agent
        return {
            "User-Agent": ua,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
        }
    
    def _generate_doc_id(self, url: str, content: str) -> str:
        """Generate a unique document ID based on URL and content hash"""
        combined = f"{url}:{content[:500]}"
        return hashlib.sha256(combined.encode()).hexdigest()[:16]
    
    def _extract_domain(self, url: str) -> str:
        """Extract domain from URL"""
        parsed = urlparse(url)
        return parsed.netloc
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10)
    )
    def _fetch_page(self, url: str) -> Optional[str]:
        """
        Fetch a single page with retry logic.
        
        Args:
            url: The URL to fetch
            
        Returns:
            HTML content as string, or None if failed
        """
        try:
            response = self.session.get(
                url,
                headers=self._get_headers(),
                timeout=30,
                allow_redirects=True
            )
            response.raise_for_status()
            return response.text
        except requests.RequestException as e:
            logger.error(f"Failed to fetch {url}: {e}")
            raise
    
    def _extract_text(self, html: str) -> tuple[str, str]:
        """
        Extract clean text and title from HTML.
        
        Args:
            html: Raw HTML content
            
        Returns:
            Tuple of (title, clean_text)
        """
        soup = BeautifulSoup(html, 'lxml')
        
        # Remove script and style elements
        for element in soup(["script", "style", "nav", "footer", "header", "aside"]):
            element.decompose()
        
        # Extract title
        title = ""
        if soup.title:
            title = soup.title.string or ""
        elif soup.find('h1'):
            title = soup.find('h1').get_text(strip=True)
        
        # Extract main content
        # Try to find main content area
        main_content = soup.find('main') or soup.find('article') or soup.find('body')
        
        if main_content:
            # Get text with proper spacing
            text = main_content.get_text(separator=' ', strip=True)
        else:
            text = soup.get_text(separator=' ', strip=True)
        
        # Clean up whitespace
        text = ' '.join(text.split())
        
        return title.strip(), text
    
    def _extract_links(self, html: str, base_url: str) -> List[str]:
        """
        Extract all valid links from HTML.
        
        Args:
            html: Raw HTML content
            base_url: Base URL for resolving relative links
            
        Returns:
            List of absolute URLs
        """
        soup = BeautifulSoup(html, 'lxml')
        links = []
        base_domain = self._extract_domain(base_url)
        
        for anchor in soup.find_all('a', href=True):
            href = anchor['href']
            
            # Skip non-http links
            if href.startswith(('mailto:', 'tel:', 'javascript:', '#')):
                continue
            
            # Convert to absolute URL
            absolute_url = urljoin(base_url, href)
            
            # Only include links from same domain
            if self._extract_domain(absolute_url) == base_domain:
                # Remove fragments
                absolute_url = absolute_url.split('#')[0]
                if absolute_url not in self.visited_urls:
                    links.append(absolute_url)
        
        return list(set(links))
    
    def scrape_page(self, url: str) -> Optional[ScrapedDocument]:
        """
        Scrape a single page and return structured document.
        
        Args:
            url: URL to scrape
            
        Returns:
            ScrapedDocument object or None if failed
        """
        if url in self.visited_urls:
            logger.debug(f"Skipping already visited URL: {url}")
            return None
        
        try:
            logger.info(f"Scraping: {url}")
            html = self._fetch_page(url)
            
            if not html:
                return None
            
            self.visited_urls.add(url)
            title, content = self._extract_text(html)
            
            # Skip pages with very little content
            if len(content) < 100:
                logger.debug(f"Skipping {url} - insufficient content")
                return None
            
            doc = ScrapedDocument(
                url=url,
                title=title,
                content=content,
                timestamp=datetime.utcnow().isoformat(),
                domain=self._extract_domain(url),
                doc_id=self._generate_doc_id(url, content),
                metadata={
                    "content_length": len(content),
                    "word_count": len(content.split())
                }
            )
            
            logger.info(f"Successfully scraped: {title[:50]}... ({len(content)} chars)")
            return doc
            
        except Exception as e:
            logger.error(f"Error scraping {url}: {e}")
            return None
    
    def crawl_website(
        self,
        start_url: str,
        max_depth: int = 2
    ) -> Generator[ScrapedDocument, None, None]:
        """
        Crawl a website starting from a URL and yield documents.
        
        Args:
            start_url: The starting URL for crawling
            max_depth: Maximum crawl depth (default: 2)
            
        Yields:
            ScrapedDocument objects for each successfully scraped page
        """
        self.visited_urls.clear()
        to_visit = [(start_url, 0)]  # (url, depth)
        pages_scraped = 0
        
        while to_visit and pages_scraped < self.max_pages:
            url, depth = to_visit.pop(0)
            
            if url in self.visited_urls:
                continue
            
            # Scrape the page
            doc = self.scrape_page(url)
            
            if doc:
                pages_scraped += 1
                yield doc
                
                # Extract links if not at max depth
                if depth < max_depth:
                    try:
                        html = self._fetch_page(url)
                        if html:
                            new_links = self._extract_links(html, url)
                            for link in new_links[:20]:  # Limit links per page
                                if link not in self.visited_urls:
                                    to_visit.append((link, depth + 1))
                    except:
                        pass
            
            # Respect rate limiting
            time.sleep(self.delay_seconds)
        
        logger.info(f"Crawl complete: {pages_scraped} pages scraped from {self._extract_domain(start_url)}")
    
    def scrape_urls(self, urls: List[str]) -> Generator[ScrapedDocument, None, None]:
        """
        Scrape a list of specific URLs.
        
        Args:
            urls: List of URLs to scrape
            
        Yields:
            ScrapedDocument objects for each successfully scraped page
        """
        for url in urls:
            doc = self.scrape_page(url)
            if doc:
                yield doc
            time.sleep(self.delay_seconds)


# Example usage and testing
if __name__ == "__main__":
    # Configure logging
    logger.add("scraper.log", rotation="10 MB")
    
    # Create scraper instance
    scraper = WebScraper(delay_seconds=1, max_pages=10)
    
    # Example: Scrape Wikipedia articles
    test_urls = [
        "https://en.wikipedia.org/wiki/Machine_learning",
        "https://en.wikipedia.org/wiki/Natural_language_processing",
        "https://en.wikipedia.org/wiki/Deep_learning"
    ]
    
    for doc in scraper.scrape_urls(test_urls):
        print(f"Scraped: {doc.title}")
        print(f"  URL: {doc.url}")
        print(f"  Content length: {len(doc.content)} characters")
        print(f"  Word count: {doc.metadata['word_count']}")
        print("---")
