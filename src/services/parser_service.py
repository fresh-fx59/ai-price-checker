"""
Parser service that orchestrates multiple parsing strategies with fallback logic.
"""
import logging
from typing import List, Optional, Dict, Any
from dataclasses import dataclass

from ..models.web_scraping import PageContent, ProductInfo
from ..parsers.product_parser import ProductParser, ParsingResult
from ..parsers.html_parser import HtmlCssParser
from ..parsers.structured_data_parser import StructuredDataParser
from ..parsers.ai_parser import AIParser


@dataclass
class ParsingAttempt:
    """Record of a parsing attempt."""
    parser_name: str
    success: bool
    confidence_score: float
    error_message: Optional[str] = None
    product_info: Optional[ProductInfo] = None


@dataclass
class ParsingServiceResult:
    """Result of the parsing service operation."""
    success: bool
    product_info: Optional[ProductInfo] = None
    best_parser: Optional[str] = None
    confidence_score: float = 0.0
    attempts: List[ParsingAttempt] = None
    error_message: Optional[str] = None
    
    def __post_init__(self):
        if self.attempts is None:
            self.attempts = []
    
    @classmethod
    def success_result(cls, product_info: ProductInfo, parser_name: str, 
                      confidence: float, attempts: List[ParsingAttempt]) -> 'ParsingServiceResult':
        """Create a successful parsing service result."""
        return cls(
            success=True,
            product_info=product_info,
            best_parser=parser_name,
            confidence_score=confidence,
            attempts=attempts
        )
    
    @classmethod
    def error_result(cls, error_message: str, attempts: List[ParsingAttempt]) -> 'ParsingServiceResult':
        """Create an error parsing service result."""
        return cls(
            success=False,
            error_message=error_message,
            attempts=attempts
        )


class ParserService:
    """Service that orchestrates multiple parsing strategies with fallback logic."""
    
    def __init__(self, ai_api_key: Optional[str] = None, ai_api_endpoint: Optional[str] = None, 
                 enable_ai_parsing: bool = True):
        """
        Initialize the parser service.
        
        Args:
            ai_api_key: API key for AI parsing service
            ai_api_endpoint: API endpoint for AI parsing service
            enable_ai_parsing: Whether to enable AI parsing
        """
        self.logger = logging.getLogger(__name__)
        self.parsers: List[ProductParser] = []
        
        # Register parsers in order of preference (highest confidence first)
        self._register_default_parsers(ai_api_key, ai_api_endpoint, enable_ai_parsing)
    
    def _register_default_parsers(self, ai_api_key: Optional[str], ai_api_endpoint: Optional[str], 
                                enable_ai_parsing: bool):
        """Register the default set of parsers."""
        # Structured data parser (highest confidence)
        self.register_parser(StructuredDataParser())
        
        # AI parser (high confidence, but optional)
        if enable_ai_parsing and ai_api_key:
            self.register_parser(AIParser(ai_api_key, ai_api_endpoint, enabled=True))
        
        # HTML/CSS parser (fallback)
        self.register_parser(HtmlCssParser())
    
    def register_parser(self, parser: ProductParser) -> None:
        """
        Register a parser with the service.
        
        Args:
            parser: Parser instance to register
        """
        self.parsers.append(parser)
        self.logger.info(f"Registered parser: {parser.name}")
    
    def parse_product(self, url: str, content: PageContent) -> ParsingServiceResult:
        """
        Parse product information using multiple strategies with fallback logic.
        
        Args:
            url: Product URL for context
            content: Page content to parse
            
        Returns:
            ParsingServiceResult with the best parsing result
        """
        attempts = []
        best_result = None
        best_confidence = 0.0
        
        self.logger.info(f"Starting product parsing for URL: {url}")
        
        # Validate input
        if not content or not content.html:
            error_msg = "Invalid or empty page content"
            self.logger.error(error_msg)
            return ParsingServiceResult.error_result(error_msg, attempts)
        
        # Try each parser that can handle the content
        for parser in self.parsers:
            try:
                # Check if parser can handle this content
                if not parser.can_parse(content):
                    self.logger.debug(f"Parser {parser.name} cannot parse this content")
                    continue
                
                self.logger.info(f"Attempting to parse with {parser.name}")
                
                # Attempt parsing
                result = parser.parse(content)
                
                # Record the attempt
                attempt = ParsingAttempt(
                    parser_name=parser.name,
                    success=result.success,
                    confidence_score=result.confidence_score,
                    error_message=result.error_message,
                    product_info=result.product_info if result.success else None
                )
                attempts.append(attempt)
                
                if result.success:
                    # Validate the product info
                    if self._validate_product_info(result.product_info):
                        self.logger.info(f"Parser {parser.name} succeeded with confidence {result.confidence_score}")
                        
                        # Keep track of the best result
                        if result.confidence_score > best_confidence:
                            best_result = result
                            best_confidence = result.confidence_score
                        
                        # If we have high confidence, we can stop here
                        if result.confidence_score >= 0.9:
                            self.logger.info(f"High confidence result from {parser.name}, stopping")
                            break
                    else:
                        self.logger.warning(f"Parser {parser.name} returned invalid product info")
                        attempt.success = False
                        attempt.error_message = "Invalid product information"
                else:
                    self.logger.warning(f"Parser {parser.name} failed: {result.error_message}")
                    
            except Exception as e:
                error_msg = f"Unexpected error in parser {parser.name}: {str(e)}"
                self.logger.error(error_msg)
                
                attempt = ParsingAttempt(
                    parser_name=parser.name,
                    success=False,
                    confidence_score=0.0,
                    error_message=error_msg
                )
                attempts.append(attempt)
        
        # Return the best result if we found one
        if best_result and best_result.success:
            self.logger.info(f"Best parsing result from {best_result.parser_name} with confidence {best_confidence}")
            return ParsingServiceResult.success_result(
                best_result.product_info,
                best_result.parser_name,
                best_confidence,
                attempts
            )
        else:
            error_msg = "All parsing attempts failed"
            self.logger.error(error_msg)
            return ParsingServiceResult.error_result(error_msg, attempts)
    
    def _validate_product_info(self, product_info: ProductInfo) -> bool:
        """
        Validate that product information meets minimum requirements.
        
        Args:
            product_info: Product information to validate
            
        Returns:
            True if valid, False otherwise
        """
        if not product_info:
            return False
        
        # Check basic validity
        if not product_info.is_valid():
            return False
        
        # Additional validation rules
        if product_info.name is not None:
            # Name should be reasonable length
            if len(product_info.name.strip()) < 2:
                return False
            
            # Name shouldn't be just numbers or symbols
            if not any(c.isalpha() for c in product_info.name):
                return False
        
        if product_info.price is not None:
            # Price should be positive
            if product_info.price <= 0:
                return False
            
            # Price should be reasonable (not too high)
            if product_info.price > 1000000:  # $1M seems like a reasonable upper limit
                return False
        
        return True
    
    def _sanitize_product_info(self, product_info: ProductInfo) -> ProductInfo:
        """
        Sanitize and clean product information.
        
        Args:
            product_info: Product information to sanitize
            
        Returns:
            Sanitized product information
        """
        if not product_info:
            return product_info
        
        # Clean name
        if product_info.name:
            # Remove excessive whitespace
            name = ' '.join(product_info.name.split())
            # Limit length
            if len(name) > 200:
                name = name[:200] + "..."
            product_info.name = name
        
        # Clean description
        if product_info.description:
            # Remove excessive whitespace
            description = ' '.join(product_info.description.split())
            # Limit length
            if len(description) > 1000:
                description = description[:1000] + "..."
            product_info.description = description
        
        # Validate image URL
        if product_info.image_url:
            # Basic URL validation
            if not (product_info.image_url.startswith('http://') or 
                   product_info.image_url.startswith('https://')):
                product_info.image_url = None
        
        # Normalize currency
        if product_info.currency:
            product_info.currency = product_info.currency.upper().strip()
        
        # Normalize availability
        if product_info.availability:
            product_info.availability = product_info.availability.strip()
        
        return product_info
    
    def get_parser_stats(self) -> Dict[str, Any]:
        """
        Get statistics about registered parsers.
        
        Returns:
            Dictionary with parser statistics
        """
        return {
            'total_parsers': len(self.parsers),
            'parser_names': [parser.name for parser in self.parsers],
            'ai_enabled': any(isinstance(parser, AIParser) and parser.enabled for parser in self.parsers)
        }
    
    def test_parsers(self, content: PageContent) -> Dict[str, bool]:
        """
        Test which parsers can handle the given content.
        
        Args:
            content: Page content to test
            
        Returns:
            Dictionary mapping parser names to whether they can parse the content
        """
        results = {}
        for parser in self.parsers:
            try:
                results[parser.name] = parser.can_parse(content)
            except Exception as e:
                self.logger.error(f"Error testing parser {parser.name}: {str(e)}")
                results[parser.name] = False
        
        return results