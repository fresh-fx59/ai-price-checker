"""
Web scraping service for fetching and processing web page content.
"""
import requests
import time
import logging
from typing import Optional, Dict, List
from urllib.parse import urlparse, urljoin
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from ..models.web_scraping import PageContent, ScrapingResult


class WebScrapingInterface:
    """Interface for web scraping operations."""
    
    def fetch_page_content(self, url: str) -> ScrapingResult:
        """Fetch content from a web page."""
        raise NotImplementedError
    
    def extract_images(self, content: PageContent) -> List[str]:
        """Extract image URLs from page content."""
        raise NotImplementedError


class WebScrapingService(WebScrapingInterface):
    """Implementation of web scraping functionality with retry logic and error handling."""
    
    def __init__(self, 
                 timeout: int = 30,
                 max_retries: int = 3,
                 backoff_factor: float = 1.0,
                 user_agent: str = None):
        """
        Initialize the web scraping service.
        
        Args:
            timeout: Request timeout in seconds
            max_retries: Maximum number of retry attempts
            backoff_factor: Factor for exponential backoff between retries
            user_agent: Custom user agent string
        """
        self.timeout = timeout
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor
        self.logger = logging.getLogger(__name__)
        
        # Default user agent to avoid being blocked
        self.user_agent = user_agent or (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        )
        
        # Configure session with retry strategy
        self.session = self._create_session()
    
    def _create_session(self) -> requests.Session:
        """Create a requests session with retry configuration."""
        session = requests.Session()
        
        # Configure retry strategy
        retry_strategy = Retry(
            total=self.max_retries,
            backoff_factor=self.backoff_factor,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS"]
        )
        
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        # Set default headers
        session.headers.update({
            'User-Agent': self.user_agent,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })
        
        return session
    
    def fetch_page_content(self, url: str) -> ScrapingResult:
        """
        Fetch content from a web page with retry logic.
        
        Args:
            url: The URL to fetch
            
        Returns:
            ScrapingResult containing the page content or error information
        """
        if not self._is_valid_url(url):
            return ScrapingResult.error_result(f"Invalid URL format: {url}")
        
        retry_count = 0
        last_error = None
        
        while retry_count <= self.max_retries:
            try:
                self.logger.info(f"Fetching URL: {url} (attempt {retry_count + 1})")
                
                response = self.session.get(
                    url,
                    timeout=self.timeout,
                    allow_redirects=True
                )
                
                # Check if the response is successful
                response.raise_for_status()
                
                # Create page content object
                page_content = PageContent(
                    url=response.url,  # Use final URL after redirects
                    html=response.text,
                    status_code=response.status_code,
                    headers=dict(response.headers),
                    encoding=response.encoding
                )
                
                self.logger.info(f"Successfully fetched {url} (status: {response.status_code})")
                return ScrapingResult.success_result(page_content)
                
            except requests.exceptions.Timeout as e:
                last_error = f"Request timeout: {str(e)}"
                self.logger.warning(f"Timeout fetching {url}: {last_error}")
                
            except requests.exceptions.ConnectionError as e:
                last_error = f"Connection error: {str(e)}"
                self.logger.warning(f"Connection error fetching {url}: {last_error}")
                
            except requests.exceptions.HTTPError as e:
                last_error = f"HTTP error {e.response.status_code}: {str(e)}"
                self.logger.warning(f"HTTP error fetching {url}: {last_error}")
                
                # Don't retry for client errors (4xx)
                if 400 <= e.response.status_code < 500:
                    retry_count += 1  # Increment to reflect the attempt
                    break
                    
            except requests.exceptions.RequestException as e:
                last_error = f"Request error: {str(e)}"
                self.logger.warning(f"Request error fetching {url}: {last_error}")
                
            except Exception as e:
                last_error = f"Unexpected error: {str(e)}"
                self.logger.error(f"Unexpected error fetching {url}: {last_error}")
                break
            
            retry_count += 1
            if retry_count <= self.max_retries:
                sleep_time = self.backoff_factor * (2 ** (retry_count - 1))
                self.logger.info(f"Retrying in {sleep_time} seconds...")
                time.sleep(sleep_time)
        
        return ScrapingResult.error_result(last_error or "Unknown error", retry_count)
    
    def extract_images(self, content: PageContent) -> List[str]:
        """
        Extract image URLs from page content.
        
        Args:
            content: PageContent object containing HTML
            
        Returns:
            List of absolute image URLs
        """
        try:
            soup = BeautifulSoup(content.html, 'html.parser')
            image_urls = []
            
            # Find all img tags
            img_tags = soup.find_all('img')
            
            for img in img_tags:
                src = img.get('src')
                if src:
                    # Convert relative URLs to absolute
                    absolute_url = urljoin(content.url, src)
                    image_urls.append(absolute_url)
                
                # Also check data-src for lazy-loaded images
                data_src = img.get('data-src')
                if data_src:
                    absolute_url = urljoin(content.url, data_src)
                    image_urls.append(absolute_url)
            
            # Remove duplicates while preserving order
            seen = set()
            unique_urls = []
            for url in image_urls:
                if url not in seen:
                    seen.add(url)
                    unique_urls.append(url)
            
            self.logger.info(f"Extracted {len(unique_urls)} image URLs from {content.url}")
            return unique_urls
            
        except Exception as e:
            self.logger.error(f"Error extracting images from {content.url}: {str(e)}")
            return []
    
    def _is_valid_url(self, url: str) -> bool:
        """
        Validate URL format.
        
        Args:
            url: URL to validate
            
        Returns:
            True if URL is valid, False otherwise
        """
        try:
            result = urlparse(url)
            # Only allow HTTP and HTTPS schemes
            return all([result.scheme, result.netloc]) and result.scheme in ['http', 'https']
        except Exception:
            return False
    
    def get_page_title(self, content: PageContent) -> Optional[str]:
        """
        Extract page title from content.
        
        Args:
            content: PageContent object
            
        Returns:
            Page title or None if not found
        """
        try:
            soup = BeautifulSoup(content.html, 'html.parser')
            title_tag = soup.find('title')
            return title_tag.get_text().strip() if title_tag else None
        except Exception as e:
            self.logger.error(f"Error extracting title from {content.url}: {str(e)}")
            return None
    
    def get_meta_description(self, content: PageContent) -> Optional[str]:
        """
        Extract meta description from content.
        
        Args:
            content: PageContent object
            
        Returns:
            Meta description or None if not found
        """
        try:
            soup = BeautifulSoup(content.html, 'html.parser')
            meta_desc = soup.find('meta', attrs={'name': 'description'})
            return meta_desc.get('content', '').strip() if meta_desc else None
        except Exception as e:
            self.logger.error(f"Error extracting meta description from {content.url}: {str(e)}")
            return None