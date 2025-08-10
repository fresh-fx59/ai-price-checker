"""
Base classes and interfaces for product information parsing.
"""
from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any
import logging
import re
from dataclasses import dataclass

from ..models.web_scraping import PageContent, ProductInfo


@dataclass
class ParsingResult:
    """Result of a product parsing operation."""
    success: bool
    product_info: Optional[ProductInfo] = None
    error_message: Optional[str] = None
    parser_name: str = ""
    confidence_score: float = 0.0  # 0.0 to 1.0
    
    @classmethod
    def success_result(cls, product_info: ProductInfo, parser_name: str, confidence: float = 1.0) -> 'ParsingResult':
        """Create a successful parsing result."""
        return cls(
            success=True,
            product_info=product_info,
            parser_name=parser_name,
            confidence_score=confidence
        )
    
    @classmethod
    def error_result(cls, error_message: str, parser_name: str) -> 'ParsingResult':
        """Create an error parsing result."""
        return cls(
            success=False,
            error_message=error_message,
            parser_name=parser_name
        )


class ProductParser(ABC):
    """Abstract base class for product information parsers."""
    
    def __init__(self, name: str):
        """
        Initialize the parser.
        
        Args:
            name: Name of the parser for identification
        """
        self.name = name
        self.logger = logging.getLogger(f"{__name__}.{name}")
    
    @abstractmethod
    def can_parse(self, content: PageContent) -> bool:
        """
        Check if this parser can handle the given content.
        
        Args:
            content: Page content to check
            
        Returns:
            True if parser can handle this content, False otherwise
        """
        pass
    
    @abstractmethod
    def parse(self, content: PageContent) -> ParsingResult:
        """
        Parse product information from page content.
        
        Args:
            content: Page content to parse
            
        Returns:
            ParsingResult containing extracted product information
        """
        pass
    
    def _clean_text(self, text: str) -> str:
        """
        Clean and normalize text content.
        
        Args:
            text: Raw text to clean
            
        Returns:
            Cleaned text
        """
        if not text:
            return ""
        
        # Remove extra whitespace and normalize
        text = re.sub(r'\s+', ' ', text.strip())
        
        # Remove common unwanted characters but keep colons
        text = re.sub(r'[^\w\s\-\.\,\$\€\£\¥\(\)\/\:]', '', text)
        
        return text
    
    def _extract_price_from_text(self, text: str) -> Optional[float]:
        """
        Extract price value from text using common patterns.
        
        Args:
            text: Text containing price information
            
        Returns:
            Extracted price as float or None if not found
        """
        if not text:
            return None
        
        # Common price patterns - order matters!
        price_patterns = [
            # US format with thousands separators (must come before European)
            r'[\$\€\£\¥]?\s*(\d{1,3}(?:,\d{3})+(?:\.\d{2})?)',  # $1,234.56, €1,234.56
            r'(\d{1,3}(?:,\d{3})+(?:\.\d{2})?)\s*[\$\€\£\¥]',   # 1,234.56$, 1,234.56€
            
            # European format (dot as thousands, comma as decimal)
            r'(\d+(?:\.\d{3})*,\d{1,2})\s*[\$\€\£\¥]?',     # 1.234,56€
            r'[\$\€\£\¥]?\s*(\d+(?:\.\d{3})*,\d{1,2})',      # €1.234,56
            
            # Simple formats
            r'(\d+,\d{1,2})\s*[\$\€\£\¥]?',                 # 123,45€ (European decimal)
            r'[\$\€\£\¥]?\s*(\d+,\d{1,2})',                 # €123,45
            r'[\$\€\£\¥]?\s*(\d+(?:\.\d{2})?)',             # $123.45, €123
            r'(\d+(?:\.\d{2})?)\s*[\$\€\£\¥]',              # 123.45$, 123€
        ]
        
        for pattern in price_patterns:
            matches = re.findall(pattern, text)
            if matches:
                try:
                    # Handle different decimal separators
                    price_str = matches[0]
                    
                    # Check if it's European format (comma as decimal separator)
                    if ',' in price_str and '.' in price_str:
                        # Format like 1.234,56 - comma is decimal separator
                        if price_str.rfind(',') > price_str.rfind('.'):
                            price_str = price_str.replace('.', '').replace(',', '.')
                        else:
                            # Format like 1,234.56 - dot is decimal separator
                            price_str = price_str.replace(',', '')
                    elif ',' in price_str and price_str.count(',') == 1:
                        # Check if comma is decimal separator (e.g., 123,45)
                        parts = price_str.split(',')
                        if len(parts) == 2 and len(parts[1]) <= 2:  # Likely decimal separator
                            price_str = price_str.replace(',', '.')
                        else:
                            # Thousands separator
                            price_str = price_str.replace(',', '')
                    else:
                        # Remove any remaining thousands separators
                        price_str = price_str.replace(',', '')
                    
                    price = float(price_str)
                    if price > 0:
                        return price
                except (ValueError, IndexError):
                    continue
        
        return None
    
    def _extract_currency_from_text(self, text: str) -> Optional[str]:
        """
        Extract currency symbol or code from text.
        
        Args:
            text: Text containing currency information
            
        Returns:
            Currency symbol/code or None if not found
        """
        if not text:
            return None
        
        # Common currency patterns
        currency_patterns = [
            (r'[\$]', 'USD'),
            (r'[€]', 'EUR'),
            (r'[£]', 'GBP'),
            (r'[¥]', 'JPY'),
            (r'\bUSD\b', 'USD'),
            (r'\bEUR\b', 'EUR'),
            (r'\bGBP\b', 'GBP'),
            (r'\bJPY\b', 'JPY'),
        ]
        
        for pattern, currency in currency_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return currency
        
        return None