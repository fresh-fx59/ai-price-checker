"""
Data models for web scraping functionality.
"""
from dataclasses import dataclass
from typing import Optional, Dict, List
from datetime import datetime


@dataclass
class PageContent:
    """Represents the content of a web page."""
    url: str
    html: str
    status_code: int
    headers: Dict[str, str]
    encoding: Optional[str] = None
    fetched_at: Optional[datetime] = None
    
    def __post_init__(self):
        if self.fetched_at is None:
            self.fetched_at = datetime.now()


@dataclass
class ProductInfo:
    """Represents extracted product information."""
    name: Optional[str] = None
    price: Optional[float] = None
    image_url: Optional[str] = None
    currency: Optional[str] = None
    availability: Optional[str] = None
    description: Optional[str] = None
    
    def is_valid(self) -> bool:
        """Check if the product info contains minimum required data."""
        return self.name is not None and self.price is not None


@dataclass
class ScrapingResult:
    """Result of a web scraping operation."""
    success: bool
    page_content: Optional[PageContent] = None
    error_message: Optional[str] = None
    retry_count: int = 0
    
    @classmethod
    def success_result(cls, page_content: PageContent) -> 'ScrapingResult':
        """Create a successful scraping result."""
        return cls(success=True, page_content=page_content)
    
    @classmethod
    def error_result(cls, error_message: str, retry_count: int = 0) -> 'ScrapingResult':
        """Create an error scraping result."""
        return cls(success=False, error_message=error_message, retry_count=retry_count)