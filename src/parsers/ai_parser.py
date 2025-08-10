"""
AI-powered parser for extracting product information from web pages.
"""
import json
import re
from typing import Optional, Dict, Any
import requests
from bs4 import BeautifulSoup

from ..models.web_scraping import PageContent, ProductInfo
from .product_parser import ProductParser, ParsingResult


class AIParser(ProductParser):
    """Parser that uses AI/LLM services to extract product information."""
    
    def __init__(self, api_key: Optional[str] = None, api_endpoint: Optional[str] = None, enabled: bool = True):
        super().__init__("AIParser")
        self.api_key = api_key
        self.api_endpoint = api_endpoint
        self.enabled = enabled and api_key is not None
        
        # Default to OpenAI-compatible endpoint if not specified
        if not self.api_endpoint and self.api_key:
            self.api_endpoint = "https://api.openai.com/v1/chat/completions"
    
    def can_parse(self, content: PageContent) -> bool:
        """
        Check if this parser can handle the given content.
        
        Args:
            content: Page content to check
            
        Returns:
            True if AI parsing is enabled and configured
        """
        return self.enabled and self.api_key is not None
    
    def parse(self, content: PageContent) -> ParsingResult:
        """
        Parse product information using AI/LLM.
        
        Args:
            content: Page content to parse
            
        Returns:
            ParsingResult with extracted product information
        """
        if not self.enabled:
            return ParsingResult.error_result("AI parsing is disabled", self.name)
        
        if not self.api_key:
            return ParsingResult.error_result("AI API key not configured", self.name)
        
        try:
            # Clean and prepare the HTML content
            cleaned_html = self._clean_html_for_ai(content.html)
            
            # Create the prompt for the AI
            prompt = self._create_extraction_prompt(cleaned_html, content.url)
            
            # Call the AI API
            response = self._call_ai_api(prompt)
            
            if response:
                product_info = self._parse_ai_response(response, content.url)
                if product_info and product_info.is_valid():
                    confidence = 0.8  # Good confidence for AI parsing
                    self.logger.info(f"AI successfully parsed product: {product_info.name} - ${product_info.price}")
                    return ParsingResult.success_result(product_info, self.name, confidence)
                else:
                    error_msg = "AI could not extract valid product information"
                    self.logger.warning(error_msg)
                    return ParsingResult.error_result(error_msg, self.name)
            else:
                error_msg = "AI API call failed"
                self.logger.error(error_msg)
                return ParsingResult.error_result(error_msg, self.name)
                
        except Exception as e:
            error_msg = f"Error in AI parsing: {str(e)}"
            self.logger.error(error_msg)
            return ParsingResult.error_result(error_msg, self.name)
    
    def _clean_html_for_ai(self, html: str) -> str:
        """
        Clean and simplify HTML content for AI processing.
        
        Args:
            html: Raw HTML content
            
        Returns:
            Cleaned HTML suitable for AI processing
        """
        try:
            soup = BeautifulSoup(html, 'html.parser')
            
            # Remove script and style elements
            for script in soup(["script", "style", "noscript"]):
                script.decompose()
            
            # Remove comments
            from bs4 import Comment
            for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
                comment.extract()
            
            # Focus on main content areas
            main_content_selectors = [
                'main',
                '[role="main"]',
                '.main-content',
                '.product-details',
                '.product-info',
                '.pdp-content',
                '#main',
                '#content',
            ]
            
            main_content = None
            for selector in main_content_selectors:
                element = soup.select_one(selector)
                if element:
                    main_content = element
                    break
            
            # If we found main content, use that; otherwise use body
            if main_content:
                content_html = str(main_content)
            else:
                body = soup.find('body')
                content_html = str(body) if body else str(soup)
            
            # Limit content length to avoid API limits
            if len(content_html) > 8000:  # Reasonable limit for most APIs
                content_html = content_html[:8000] + "..."
            
            return content_html
            
        except Exception as e:
            self.logger.warning(f"Error cleaning HTML: {str(e)}")
            # Return truncated original HTML as fallback
            return html[:8000] + "..." if len(html) > 8000 else html
    
    def _create_extraction_prompt(self, html_content: str, url: str) -> str:
        """
        Create a prompt for the AI to extract product information.
        
        Args:
            html_content: Cleaned HTML content
            url: Product page URL
            
        Returns:
            Formatted prompt for AI
        """
        prompt = f"""
You are a web scraping expert. Extract product information from the following HTML content from URL: {url}

Please extract the following information and return it as a JSON object:
- name: Product name/title
- price: Numeric price value (just the number, no currency symbols)
- currency: Currency code (USD, EUR, GBP, etc.)
- image_url: Main product image URL (make it absolute if relative)
- availability: Stock status (In Stock, Out of Stock, etc.)
- description: Brief product description

Rules:
1. Return ONLY a valid JSON object, no other text
2. If you cannot find a field, set it to null
3. For price, extract only the numeric value (e.g., 29.99, not $29.99)
4. For image_url, make sure it's a complete URL
5. Be conservative - only extract information you're confident about

HTML Content:
{html_content}

JSON Response:
"""
        return prompt
    
    def _call_ai_api(self, prompt: str) -> Optional[Dict[str, Any]]:
        """
        Call the AI API to process the prompt.
        
        Args:
            prompt: The prompt to send to the AI
            
        Returns:
            API response data or None if failed
        """
        try:
            headers = {
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json',
            }
            
            # OpenAI-compatible API format
            payload = {
                'model': 'gpt-3.5-turbo',  # Default model
                'messages': [
                    {
                        'role': 'user',
                        'content': prompt
                    }
                ],
                'max_tokens': 500,
                'temperature': 0.1,  # Low temperature for consistent extraction
            }
            
            response = requests.post(
                self.api_endpoint,
                headers=headers,
                json=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                self.logger.error(f"AI API error: {response.status_code} - {response.text}")
                return None
                
        except requests.exceptions.RequestException as e:
            self.logger.error(f"AI API request failed: {str(e)}")
            return None
        except Exception as e:
            self.logger.error(f"Unexpected error calling AI API: {str(e)}")
            return None
    
    def _parse_ai_response(self, response: Dict[str, Any], base_url: str) -> Optional[ProductInfo]:
        """
        Parse the AI API response to extract product information.
        
        Args:
            response: AI API response
            base_url: Base URL for resolving relative URLs
            
        Returns:
            ProductInfo object or None if parsing failed
        """
        try:
            # Extract the content from OpenAI-style response
            choices = response.get('choices', [])
            if not choices:
                self.logger.error("No choices in AI response")
                return None
            
            content = choices[0].get('message', {}).get('content', '')
            if not content:
                self.logger.error("No content in AI response")
                return None
            
            # Try to parse JSON from the response
            # Sometimes AI includes extra text, so try to extract JSON
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                json_str = json_match.group()
            else:
                json_str = content.strip()
            
            try:
                data = json.loads(json_str)
            except json.JSONDecodeError:
                # Try to clean up common JSON issues
                json_str = re.sub(r',\s*}', '}', json_str)  # Remove trailing commas
                json_str = re.sub(r',\s*]', ']', json_str)
                data = json.loads(json_str)
            
            # Extract and validate the data
            name = data.get('name')
            price = data.get('price')
            currency = data.get('currency')
            image_url = data.get('image_url')
            availability = data.get('availability')
            description = data.get('description')
            
            # Convert price to float if it's a string
            if isinstance(price, str):
                try:
                    price = float(re.sub(r'[^\d\.]', '', price))
                except (ValueError, TypeError):
                    price = None
            
            # Make image URL absolute if it's relative
            if image_url and not image_url.startswith(('http://', 'https://')):
                from urllib.parse import urljoin
                image_url = urljoin(base_url, image_url)
            
            return ProductInfo(
                name=name if name else None,
                price=price,
                image_url=image_url if image_url else None,
                currency=currency if currency else None,
                availability=availability if availability else None,
                description=description if description else None
            )
            
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            self.logger.error(f"Error parsing AI response: {str(e)}")
            self.logger.debug(f"AI response content: {response}")
            return None
        except Exception as e:
            self.logger.error(f"Unexpected error parsing AI response: {str(e)}")
            return None