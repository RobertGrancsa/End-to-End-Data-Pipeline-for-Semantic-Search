"""
Content Extractor Module

Advanced content extraction utilities for cleaning and processing HTML.

Author: Rares-Alexandru Constantin
"""

import re
from typing import Dict, List, Optional, Tuple
from bs4 import BeautifulSoup, NavigableString
from dataclasses import dataclass
from loguru import logger


@dataclass
class ExtractedContent:
    """Structured extracted content"""
    title: str
    main_content: str
    headings: List[str]
    paragraphs: List[str]
    links: List[Dict[str, str]]
    images: List[Dict[str, str]]
    metadata: Dict[str, str]


class ContentExtractor:
    """
    Advanced content extractor that provides structured extraction
    of web page content with semantic understanding.
    """
    
    # Elements to remove entirely
    REMOVE_ELEMENTS = [
        'script', 'style', 'noscript', 'iframe', 'svg',
        'nav', 'footer', 'header', 'aside', 'form',
        'button', 'input', 'select', 'textarea'
    ]
    
    # Elements that typically contain main content
    MAIN_CONTENT_SELECTORS = [
        'article',
        'main',
        '[role="main"]',
        '.post-content',
        '.article-content',
        '.entry-content',
        '.content',
        '#content',
        '.post',
        '.article'
    ]
    
    def __init__(self, min_text_length: int = 50):
        """
        Initialize the content extractor.
        
        Args:
            min_text_length: Minimum text length for a paragraph to be included
        """
        self.min_text_length = min_text_length
    
    def _clean_text(self, text: str) -> str:
        """Clean and normalize text"""
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text)
        # Remove special characters but keep punctuation
        text = re.sub(r'[^\w\s.,!?;:\'"()-]', '', text)
        return text.strip()
    
    def _extract_metadata(self, soup: BeautifulSoup) -> Dict[str, str]:
        """Extract metadata from HTML head"""
        metadata = {}
        
        # Extract meta tags
        for meta in soup.find_all('meta'):
            name = meta.get('name') or meta.get('property', '')
            content = meta.get('content', '')
            
            if name and content:
                # Focus on common metadata
                if name.lower() in ['description', 'keywords', 'author', 'og:title', 
                                    'og:description', 'article:published_time']:
                    metadata[name.lower().replace(':', '_')] = content
        
        # Extract canonical URL
        canonical = soup.find('link', rel='canonical')
        if canonical:
            metadata['canonical_url'] = canonical.get('href', '')
        
        return metadata
    
    def _find_main_content(self, soup: BeautifulSoup) -> Optional[BeautifulSoup]:
        """Find the main content area of the page"""
        for selector in self.MAIN_CONTENT_SELECTORS:
            element = soup.select_one(selector)
            if element:
                return element
        
        # Fallback to body
        return soup.find('body')
    
    def _extract_headings(self, soup: BeautifulSoup) -> List[str]:
        """Extract all headings from content"""
        headings = []
        for level in range(1, 7):
            for heading in soup.find_all(f'h{level}'):
                text = heading.get_text(strip=True)
                if text:
                    headings.append(f"H{level}: {text}")
        return headings
    
    def _extract_paragraphs(self, soup: BeautifulSoup) -> List[str]:
        """Extract paragraphs with sufficient content"""
        paragraphs = []
        
        for p in soup.find_all('p'):
            text = p.get_text(strip=True)
            if len(text) >= self.min_text_length:
                paragraphs.append(self._clean_text(text))
        
        return paragraphs
    
    def _extract_links(self, soup: BeautifulSoup, base_url: str = "") -> List[Dict[str, str]]:
        """Extract links with text and href"""
        links = []
        
        for a in soup.find_all('a', href=True):
            href = a['href']
            text = a.get_text(strip=True)
            
            if text and not href.startswith(('#', 'javascript:', 'mailto:')):
                links.append({
                    'text': text[:100],  # Limit text length
                    'href': href
                })
        
        return links[:50]  # Limit number of links
    
    def _extract_images(self, soup: BeautifulSoup) -> List[Dict[str, str]]:
        """Extract images with alt text"""
        images = []
        
        for img in soup.find_all('img'):
            src = img.get('src') or img.get('data-src', '')
            alt = img.get('alt', '')
            
            if src:
                images.append({
                    'src': src,
                    'alt': alt
                })
        
        return images[:20]  # Limit number of images
    
    def _get_text_density(self, element) -> float:
        """Calculate text density of an element (text length / tag count)"""
        text_length = len(element.get_text(strip=True))
        tag_count = len(element.find_all()) + 1
        return text_length / tag_count
    
    def extract(self, html: str, url: str = "") -> ExtractedContent:
        """
        Extract structured content from HTML.
        
        Args:
            html: Raw HTML content
            url: Original URL (optional, for resolving links)
            
        Returns:
            ExtractedContent object with structured data
        """
        soup = BeautifulSoup(html, 'lxml')
        
        # Remove unwanted elements
        for tag in self.REMOVE_ELEMENTS:
            for element in soup.find_all(tag):
                element.decompose()
        
        # Extract title
        title = ""
        if soup.title:
            title = soup.title.string or ""
        elif soup.find('h1'):
            title = soup.find('h1').get_text(strip=True)
        
        # Extract metadata
        metadata = self._extract_metadata(soup)
        
        # Find main content
        main_element = self._find_main_content(soup)
        
        if main_element:
            # Extract components
            headings = self._extract_headings(main_element)
            paragraphs = self._extract_paragraphs(main_element)
            links = self._extract_links(main_element, url)
            images = self._extract_images(main_element)
            
            # Get full text content
            main_content = main_element.get_text(separator=' ', strip=True)
            main_content = ' '.join(main_content.split())
        else:
            headings = []
            paragraphs = []
            links = []
            images = []
            main_content = ""
        
        return ExtractedContent(
            title=self._clean_text(title),
            main_content=main_content,
            headings=headings,
            paragraphs=paragraphs,
            links=links,
            images=images,
            metadata=metadata
        )
    
    def extract_for_embedding(self, html: str) -> str:
        """
        Extract text optimized for embedding generation.
        
        This returns clean text suitable for chunking and vectorization.
        
        Args:
            html: Raw HTML content
            
        Returns:
            Clean text string optimized for embeddings
        """
        content = self.extract(html)
        
        # Combine title and content
        parts = []
        
        if content.title:
            parts.append(content.title)
        
        # Add headings as context
        for heading in content.headings[:5]:  # Top 5 headings
            parts.append(heading.split(': ', 1)[-1])
        
        # Add main content
        if content.main_content:
            parts.append(content.main_content)
        
        return ' '.join(parts)


# Example usage
if __name__ == "__main__":
    sample_html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Sample Article</title>
        <meta name="description" content="A sample article for testing">
    </head>
    <body>
        <nav>Navigation here</nav>
        <main>
            <article>
                <h1>Main Heading</h1>
                <p>This is the first paragraph with enough content to be extracted properly.</p>
                <h2>Subheading</h2>
                <p>Another paragraph with meaningful content that should definitely be included.</p>
                <a href="https://example.com">Example Link</a>
            </article>
        </main>
        <footer>Footer content</footer>
    </body>
    </html>
    """
    
    extractor = ContentExtractor()
    result = extractor.extract(sample_html)
    
    print(f"Title: {result.title}")
    print(f"Headings: {result.headings}")
    print(f"Paragraphs: {len(result.paragraphs)}")
    print(f"Content length: {len(result.main_content)}")
