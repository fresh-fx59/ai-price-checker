"""
Parser for structured data (JSON-LD, microdata) from web pages.
"""
import json
import re
from typing import Optional, List, Dict, Any
from bs4 import BeautifulSoup
from urllib.parse import urljoin

from ..models.web_scraping import PageContent, ProductInfo
from .product_parser import ProductParser, ParsingResult


class StructuredDataParser(ProductParser):
    """Parser that extracts product information from structured data."""
    
    def __init__(self):
        super().__init__("StructuredDataParser")
    
    def can_parse(self, content: PageContent) -> bool:
        """
        Check if this parser can handle the given content.
        
        Args:
            content: Page content to check
            
        Returns:
            True if structured data is found
        """
        try:
            soup = BeautifulSoup(content.html, 'html.parser')
            
            # Check for JSON-LD structured data
            json_ld_scripts = soup.find_all('script', type='application/ld+json')
            if json_ld_scripts:
                for script in json_ld_scripts:
                    try:
                        data = json.loads(script.string or '')
                        if self._contains_product_data(data):
                            return True
                    except (json.JSONDecodeError, TypeError):
                        continue
            
            # Check for microdata
            if soup.find(attrs={'itemtype': re.compile(r'schema\.org/Product')}):
                return True
            
            # Check for RDFa
            if soup.find(attrs={'typeof': re.compile(r'Product')}):
                return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"Error checking structured data: {str(e)}")
            return False
    
    def parse(self, content: PageContent) -> ParsingResult:
        """
        Parse product information from structured data.
        
        Args:
            content: Page content to parse
            
        Returns:
            ParsingResult with extracted product information
        """
        try:
            soup = BeautifulSoup(content.html, 'html.parser')
            
            # Try JSON-LD first (most reliable)
            product_info = self._parse_json_ld(soup, content.url)
            
            # If JSON-LD didn't work, try microdata
            if not product_info or not product_info.is_valid():
                microdata_info = self._parse_microdata(soup, content.url)
                if microdata_info and microdata_info.is_valid():
                    product_info = microdata_info
            
            # If still no valid data, try RDFa
            if not product_info or not product_info.is_valid():
                rdfa_info = self._parse_rdfa(soup, content.url)
                if rdfa_info and rdfa_info.is_valid():
                    product_info = rdfa_info
            
            if product_info and product_info.is_valid():
                confidence = 0.9  # High confidence for structured data
                self.logger.info(f"Successfully parsed structured data: {product_info.name} - ${product_info.price}")
                return ParsingResult.success_result(product_info, self.name, confidence)
            else:
                error_msg = "No valid product structured data found"
                self.logger.warning(error_msg)
                return ParsingResult.error_result(error_msg, self.name)
                
        except Exception as e:
            error_msg = f"Error parsing structured data: {str(e)}"
            self.logger.error(error_msg)
            return ParsingResult.error_result(error_msg, self.name)
    
    def _contains_product_data(self, data: Any) -> bool:
        """Check if JSON-LD data contains product information."""
        if isinstance(data, dict):
            # Check @type field
            type_field = data.get('@type', '')
            if isinstance(type_field, str) and 'Product' in type_field:
                return True
            elif isinstance(type_field, list) and any('Product' in t for t in type_field):
                return True
            
            # Check nested objects
            for value in data.values():
                if self._contains_product_data(value):
                    return True
        
        elif isinstance(data, list):
            for item in data:
                if self._contains_product_data(item):
                    return True
        
        return False
    
    def _parse_json_ld(self, soup: BeautifulSoup, base_url: str) -> Optional[ProductInfo]:
        """Parse JSON-LD structured data."""
        json_ld_scripts = soup.find_all('script', type='application/ld+json')
        
        for script in json_ld_scripts:
            try:
                if not script.string:
                    continue
                
                data = json.loads(script.string)
                product_data = self._find_product_in_json_ld(data)
                
                if product_data:
                    return self._extract_product_from_json_ld(product_data, base_url)
                    
            except (json.JSONDecodeError, TypeError) as e:
                self.logger.warning(f"Error parsing JSON-LD: {str(e)}")
                continue
        
        return None
    
    def _find_product_in_json_ld(self, data: Any) -> Optional[Dict]:
        """Find product data within JSON-LD structure."""
        if isinstance(data, dict):
            # Check if this is a product
            type_field = data.get('@type', '')
            if isinstance(type_field, str) and 'Product' in type_field:
                return data
            elif isinstance(type_field, list) and any('Product' in t for t in type_field):
                return data
            
            # Search in nested objects
            for value in data.values():
                result = self._find_product_in_json_ld(value)
                if result:
                    return result
        
        elif isinstance(data, list):
            for item in data:
                result = self._find_product_in_json_ld(item)
                if result:
                    return result
        
        return None
    
    def _extract_product_from_json_ld(self, data: Dict, base_url: str) -> ProductInfo:
        """Extract product information from JSON-LD data."""
        name = data.get('name', '')
        
        # Extract price from offers
        price = None
        currency = None
        availability = None
        
        offers = data.get('offers', data.get('offer', []))
        if not isinstance(offers, list):
            offers = [offers]
        
        for offer in offers:
            if isinstance(offer, dict):
                # Get price
                offer_price = offer.get('price')
                if offer_price and not price:
                    try:
                        price = float(offer_price)
                    except (ValueError, TypeError):
                        pass
                
                # Get currency
                if not currency:
                    currency = offer.get('priceCurrency', '')
                    if not currency:
                        currency = offer.get('currency', '')
                    # Clean up currency value
                    if currency:
                        currency = currency.strip()
                
                # Get availability
                if not availability:
                    avail = offer.get('availability', '')
                    if avail:
                        availability = self._normalize_availability(avail)
        
        # Extract image
        image_url = None
        image_data = data.get('image', [])
        if isinstance(image_data, str):
            image_url = urljoin(base_url, image_data)
        elif isinstance(image_data, list) and image_data:
            first_image = image_data[0]
            if isinstance(first_image, str):
                image_url = urljoin(base_url, first_image)
            elif isinstance(first_image, dict):
                url = first_image.get('url', first_image.get('@id', ''))
                if url:
                    image_url = urljoin(base_url, url)
        elif isinstance(image_data, dict):
            url = image_data.get('url', image_data.get('@id', ''))
            if url:
                image_url = urljoin(base_url, url)
        
        # Extract description
        description = data.get('description', '')
        
        return ProductInfo(
            name=name if name else None,
            price=price,
            image_url=image_url,
            currency=currency if currency else None,
            availability=availability,
            description=description if description else None
        )
    
    def _parse_microdata(self, soup: BeautifulSoup, base_url: str) -> Optional[ProductInfo]:
        """Parse microdata structured data."""
        # Find product microdata
        product_element = soup.find(attrs={'itemtype': re.compile(r'schema\.org/Product')})
        if not product_element:
            return None
        
        # Extract name
        name_element = product_element.find(attrs={'itemprop': 'name'})
        name = name_element.get_text(strip=True) if name_element else None
        
        # Extract price from offers
        price = None
        currency = None
        availability = None
        
        offers_elements = product_element.find_all(attrs={'itemprop': 'offers'})
        for offers_element in offers_elements:
            # Look for price
            price_element = offers_element.find(attrs={'itemprop': 'price'})
            if price_element:
                price_text = price_element.get('content', price_element.get_text(strip=True))
                try:
                    price = float(price_text)
                except (ValueError, TypeError):
                    pass
            
            # Look for currency within the offers element
            if not currency:
                currency_element = offers_element.find(attrs={'itemprop': 'priceCurrency'})
                if currency_element:
                    currency = currency_element.get('content', currency_element.get_text(strip=True))
            
            # Look for availability
            if not availability:
                avail_element = offers_element.find(attrs={'itemprop': 'availability'})
                if avail_element:
                    avail_text = avail_element.get('href', avail_element.get_text(strip=True))
                    availability = self._normalize_availability(avail_text)
        
        # If we found price but no currency in offers, look in the product element
        if price and not currency:
            currency_element = product_element.find(attrs={'itemprop': 'priceCurrency'})
            if currency_element:
                currency = currency_element.get('content', currency_element.get_text(strip=True))
        
        # Extract image
        image_url = None
        image_element = product_element.find(attrs={'itemprop': 'image'})
        if image_element:
            src = image_element.get('src', image_element.get('content', ''))
            if src:
                image_url = urljoin(base_url, src)
        
        # Extract description
        description = None
        desc_element = product_element.find(attrs={'itemprop': 'description'})
        if desc_element:
            description = desc_element.get_text(strip=True)
        
        return ProductInfo(
            name=name,
            price=price,
            image_url=image_url,
            currency=currency,
            availability=availability,
            description=description
        )
    
    def _parse_rdfa(self, soup: BeautifulSoup, base_url: str) -> Optional[ProductInfo]:
        """Parse RDFa structured data."""
        # Find product RDFa
        product_element = soup.find(attrs={'typeof': re.compile(r'Product')})
        if not product_element:
            return None
        
        # Extract name
        name_element = product_element.find(attrs={'property': 'name'})
        name = name_element.get_text(strip=True) if name_element else None
        
        # Extract price
        price = None
        price_element = product_element.find(attrs={'property': re.compile(r'price')})
        if price_element:
            price_text = price_element.get('content', price_element.get_text(strip=True))
            try:
                price = float(price_text)
            except (ValueError, TypeError):
                pass
        
        # Extract image
        image_url = None
        image_element = product_element.find(attrs={'property': 'image'})
        if image_element:
            src = image_element.get('src', image_element.get('content', ''))
            if src:
                image_url = urljoin(base_url, src)
        
        return ProductInfo(
            name=name,
            price=price,
            image_url=image_url
        )
    
    def _normalize_availability(self, availability_text: str) -> str:
        """Normalize availability text to standard values."""
        if not availability_text:
            return ""
        
        text_lower = availability_text.lower()
        
        if any(term in text_lower for term in ['instock', 'in_stock', 'available']):
            return 'In Stock'
        elif any(term in text_lower for term in ['outofstock', 'out_of_stock', 'soldout']):
            return 'Out of Stock'
        elif 'limitedavailability' in text_lower:
            return 'Limited Availability'
        elif 'preorder' in text_lower:
            return 'Pre-order'
        else:
            return availability_text