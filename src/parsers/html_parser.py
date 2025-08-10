"""
HTML/CSS selector-based parser for common e-commerce patterns.
"""
from typing import Optional, List, Dict, Any
from bs4 import BeautifulSoup, Tag
from urllib.parse import urljoin
import re

from ..models.web_scraping import PageContent, ProductInfo
from .product_parser import ProductParser, ParsingResult


class HtmlCssParser(ProductParser):
    """Parser that uses HTML/CSS selectors to extract product information."""
    
    def __init__(self):
        super().__init__("HtmlCssParser")
        
        # Common CSS selectors for product information
        self.name_selectors = [
            'h1',
            '[data-testid*="product-title"]',
            '[data-testid*="product-name"]',
            '.product-title',
            '.product-name',
            '.product-header h1',
            '.pdp-product-name',
            '#product-title',
            '[itemprop="name"]',
            '.entry-title',
            '.product_title',
        ]
        
        self.price_selectors = [
            '[data-testid*="price"]',
            '.price',
            '.product-price',
            '.current-price',
            '.sale-price',
            '.price-current',
            '.price-now',
            '[itemprop="price"]',
            '[data-price]',
            '.price-box .price',
            '.pdp-price',
            '.product-price-value',
            '.price-display',
        ]
        
        self.image_selectors = [
            '[data-testid*="product-image"] img',
            '.product-image img',
            '.product-image',  # img tag itself might have the class
            '.product-photo img',
            '.product-photo',
            '.product-gallery img',
            '.pdp-image img',
            '[itemprop="image"]',
            '.main-image img',
            '.main-image',
            '.hero-image img',
            '.hero-image',
            '.product-img img',
            '.product-img',
            'img.product-image',  # explicit img with class
        ]
    
    def can_parse(self, content: PageContent) -> bool:
        """
        Check if this parser can handle the given content.
        
        Args:
            content: Page content to check
            
        Returns:
            True if content appears to be a product page
        """
        try:
            soup = BeautifulSoup(content.html, 'html.parser')
            
            # Look for common e-commerce indicators
            indicators = [
                # Common product page elements
                soup.find(attrs={'itemtype': re.compile(r'schema\.org/Product')}),
                soup.find('meta', attrs={'property': 'product:price:amount'}),
                soup.find('meta', attrs={'property': 'og:type', 'content': 'product'}),
                
                # Common class patterns - check separately for better detection
                soup.find(class_=re.compile(r'product', re.I)),
                soup.find(class_=re.compile(r'price', re.I)),
                soup.find(id=re.compile(r'product|price', re.I)),
                
                # Shopping cart or buy buttons
                soup.find(string=re.compile(r'add to cart|buy now|purchase', re.I)),
                soup.find(attrs={'data-testid': re.compile(r'add.*cart|buy', re.I)}),
            ]
            
            # If we find at least 2 indicators, consider it parseable
            found_indicators = sum(1 for indicator in indicators if indicator)
            return found_indicators >= 2
            
        except Exception as e:
            self.logger.error(f"Error checking if content can be parsed: {str(e)}")
            return False
    
    def parse(self, content: PageContent) -> ParsingResult:
        """
        Parse product information using CSS selectors.
        
        Args:
            content: Page content to parse
            
        Returns:
            ParsingResult with extracted product information
        """
        try:
            soup = BeautifulSoup(content.html, 'html.parser')
            
            # Extract product information
            name = self._extract_product_name(soup)
            price = self._extract_product_price(soup)
            image_url = self._extract_product_image(soup, content.url)
            currency = self._extract_currency(soup)
            availability = self._extract_availability(soup)
            description = self._extract_description(soup)
            
            # Create product info
            product_info = ProductInfo(
                name=name,
                price=price,
                image_url=image_url,
                currency=currency,
                availability=availability,
                description=description
            )
            
            # Calculate confidence score based on what we found
            confidence = self._calculate_confidence(product_info)
            
            if product_info.is_valid():
                self.logger.info(f"Successfully parsed product: {name} - ${price}")
                return ParsingResult.success_result(product_info, self.name, confidence)
            else:
                error_msg = "Could not extract minimum required product information (name and price)"
                self.logger.warning(f"Parsing failed: {error_msg}")
                return ParsingResult.error_result(error_msg, self.name)
                
        except Exception as e:
            error_msg = f"Error parsing HTML content: {str(e)}"
            self.logger.error(error_msg)
            return ParsingResult.error_result(error_msg, self.name)
    
    def _extract_product_name(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract product name using CSS selectors."""
        for selector in self.name_selectors:
            try:
                element = soup.select_one(selector)
                if element:
                    text = element.get_text(strip=True)
                    if text and len(text) > 3:  # Reasonable name length
                        return self._clean_text(text)
            except Exception:
                continue
        
        # Fallback to page title if no specific product name found
        title_tag = soup.find('title')
        if title_tag:
            title = title_tag.get_text(strip=True)
            # Remove common suffixes from title
            title = re.sub(r'\s*[-|]\s*(Amazon|eBay|Shop|Store|Buy).*$', '', title, flags=re.I)
            if title and len(title) > 3:
                return self._clean_text(title)
        
        return None
    
    def _extract_product_price(self, soup: BeautifulSoup) -> Optional[float]:
        """Extract product price using CSS selectors."""
        for selector in self.price_selectors:
            try:
                elements = soup.select(selector)
                for element in elements:
                    # Try different ways to get price text
                    price_texts = [
                        element.get_text(strip=True),
                        element.get('content', ''),
                        element.get('data-price', ''),
                        element.get('value', ''),
                    ]
                    
                    for price_text in price_texts:
                        if price_text:
                            price = self._extract_price_from_text(price_text)
                            if price:
                                return price
            except Exception:
                continue
        
        # Fallback: search for price patterns in meta tags
        meta_price_selectors = [
            'meta[property="product:price:amount"]',
            'meta[property="og:price:amount"]',
            'meta[name="price"]',
            'meta[itemprop="price"]',
        ]
        
        for selector in meta_price_selectors:
            try:
                element = soup.select_one(selector)
                if element:
                    content = element.get('content', '')
                    if content:
                        price = self._extract_price_from_text(content)
                        if price:
                            return price
            except Exception:
                continue
        
        return None
    
    def _extract_product_image(self, soup: BeautifulSoup, base_url: str) -> Optional[str]:
        """Extract product image URL using CSS selectors."""
        for selector in self.image_selectors:
            try:
                element = soup.select_one(selector)
                if element:
                    # Try different image source attributes
                    img_sources = [
                        element.get('src'),
                        element.get('data-src'),
                        element.get('data-lazy-src'),
                        element.get('data-original'),
                    ]
                    
                    for src in img_sources:
                        if src and not src.startswith('data:'):  # Skip data URLs
                            # Convert relative URLs to absolute
                            absolute_url = urljoin(base_url, src)
                            # Basic validation that it looks like an image URL or just return any valid URL
                            if re.search(r'\.(jpg|jpeg|png|gif|webp)(\?|$)', absolute_url, re.I) or src:
                                return absolute_url
            except Exception:
                continue
        
        # Fallback: look for Open Graph image
        try:
            og_image = soup.select_one('meta[property="og:image"]')
            if og_image:
                src = og_image.get('content')
                if src:
                    return urljoin(base_url, src)
        except Exception:
            pass
        
        return None
    
    def _extract_currency(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract currency information."""
        # Look in meta tags first
        currency_selectors = [
            'meta[property="product:price:currency"]',
            'meta[property="og:price:currency"]',
            'meta[name="currency"]',
        ]
        
        for selector in currency_selectors:
            try:
                element = soup.select_one(selector)
                if element:
                    currency = element.get('content', '').strip().upper()
                    if currency:
                        return currency
            except Exception:
                continue
        
        # Look for currency symbols in price elements
        for selector in self.price_selectors:
            try:
                element = soup.select_one(selector)
                if element:
                    text = element.get_text(strip=True)
                    currency = self._extract_currency_from_text(text)
                    if currency:
                        return currency
            except Exception:
                continue
        
        return None
    
    def _extract_availability(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract product availability status."""
        availability_selectors = [
            '[data-testid*="availability"]',
            '.availability',
            '.stock-status',
            '.product-availability',
            '[itemprop="availability"]',
        ]
        
        for selector in availability_selectors:
            try:
                element = soup.select_one(selector)
                if element:
                    text = element.get_text(strip=True)
                    if text:
                        # Normalize availability text
                        text_lower = text.lower()
                        if any(word in text_lower for word in ['in stock', 'available', 'ready']):
                            return 'In Stock'
                        elif any(word in text_lower for word in ['out of stock', 'unavailable', 'sold out']):
                            return 'Out of Stock'
                        else:
                            return self._clean_text(text)
            except Exception:
                continue
        
        return None
    
    def _extract_description(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract product description."""
        description_selectors = [
            '[data-testid*="description"]',
            '.product-description',
            '.product-details',
            '.description',
            '[itemprop="description"]',
            '.product-summary',
        ]
        
        for selector in description_selectors:
            try:
                element = soup.select_one(selector)
                if element:
                    text = element.get_text(strip=True)
                    if text and len(text) > 10:  # Reasonable description length
                        # Truncate very long descriptions
                        if len(text) > 500:
                            text = text[:500] + "..."
                        return self._clean_text(text)
            except Exception:
                continue
        
        # Fallback to meta description
        try:
            meta_desc = soup.select_one('meta[name="description"]')
            if meta_desc:
                content = meta_desc.get('content', '').strip()
                if content and len(content) > 10:
                    return self._clean_text(content)
        except Exception:
            pass
        
        return None
    
    def _calculate_confidence(self, product_info: ProductInfo) -> float:
        """
        Calculate confidence score based on extracted information.
        
        Args:
            product_info: Extracted product information
            
        Returns:
            Confidence score between 0.0 and 1.0
        """
        score = 0.0
        
        # Base score for having name and price (required)
        if product_info.name:
            score += 0.4
        if product_info.price:
            score += 0.4
        
        # Bonus points for additional information
        if product_info.image_url:
            score += 0.1
        if product_info.currency:
            score += 0.05
        if product_info.availability:
            score += 0.03
        if product_info.description:
            score += 0.02
        
        return min(score, 1.0)