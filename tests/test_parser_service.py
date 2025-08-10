"""
Tests for parser service functionality.
"""
import unittest
from unittest.mock import Mock, patch

from src.models.web_scraping import PageContent, ProductInfo
from src.services.parser_service import ParserService, ParsingServiceResult, ParsingAttempt
from src.parsers.product_parser import ProductParser, ParsingResult


class MockParser(ProductParser):
    """Mock parser for testing."""
    
    def __init__(self, name: str, can_parse_result: bool = True, 
                 parse_success: bool = True, confidence: float = 0.8,
                 product_info: ProductInfo = None):
        super().__init__(name)
        self.can_parse_result = can_parse_result
        self.parse_success = parse_success
        self.confidence = confidence
        self.product_info = product_info or ProductInfo(name="Test Product", price=29.99)
    
    def can_parse(self, content: PageContent) -> bool:
        return self.can_parse_result
    
    def parse(self, content: PageContent) -> ParsingResult:
        if self.parse_success:
            return ParsingResult.success_result(self.product_info, self.name, self.confidence)
        else:
            return ParsingResult.error_result("Mock parsing failed", self.name)


class TestParsingAttempt(unittest.TestCase):
    """Test cases for ParsingAttempt class."""
    
    def test_parsing_attempt_creation(self):
        """Test creating a parsing attempt."""
        product_info = ProductInfo(name="Test", price=10.0)
        attempt = ParsingAttempt(
            parser_name="TestParser",
            success=True,
            confidence_score=0.8,
            product_info=product_info
        )
        
        self.assertEqual(attempt.parser_name, "TestParser")
        self.assertTrue(attempt.success)
        self.assertEqual(attempt.confidence_score, 0.8)
        self.assertEqual(attempt.product_info, product_info)
        self.assertIsNone(attempt.error_message)


class TestParsingServiceResult(unittest.TestCase):
    """Test cases for ParsingServiceResult class."""
    
    def test_success_result_creation(self):
        """Test creating a successful service result."""
        product_info = ProductInfo(name="Test Product", price=29.99)
        attempts = [ParsingAttempt("TestParser", True, 0.8)]
        
        result = ParsingServiceResult.success_result(
            product_info, "TestParser", 0.8, attempts
        )
        
        self.assertTrue(result.success)
        self.assertEqual(result.product_info, product_info)
        self.assertEqual(result.best_parser, "TestParser")
        self.assertEqual(result.confidence_score, 0.8)
        self.assertEqual(result.attempts, attempts)
        self.assertIsNone(result.error_message)
    
    def test_error_result_creation(self):
        """Test creating an error service result."""
        attempts = [ParsingAttempt("TestParser", False, 0.0, error_message="Failed")]
        error_msg = "All parsers failed"
        
        result = ParsingServiceResult.error_result(error_msg, attempts)
        
        self.assertFalse(result.success)
        self.assertIsNone(result.product_info)
        self.assertIsNone(result.best_parser)
        self.assertEqual(result.confidence_score, 0.0)
        self.assertEqual(result.attempts, attempts)
        self.assertEqual(result.error_message, error_msg)


class TestParserService(unittest.TestCase):
    """Test cases for ParserService."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create service without default parsers for controlled testing
        self.service = ParserService.__new__(ParserService)
        self.service.logger = Mock()
        self.service.parsers = []
        
        # Sample page content
        self.page_content = PageContent(
            url="https://example.com/product",
            html="<html><body><h1>Test Product</h1><div class='price'>$29.99</div></body></html>",
            status_code=200,
            headers={}
        )
    
    def test_register_parser(self):
        """Test registering a parser."""
        parser = MockParser("TestParser")
        
        self.service.register_parser(parser)
        
        self.assertEqual(len(self.service.parsers), 1)
        self.assertEqual(self.service.parsers[0], parser)
    
    def test_parse_product_success_single_parser(self):
        """Test successful parsing with a single parser."""
        product_info = ProductInfo(name="Test Product", price=29.99)
        parser = MockParser("TestParser", parse_success=True, product_info=product_info)
        self.service.register_parser(parser)
        
        result = self.service.parse_product("https://example.com/product", self.page_content)
        
        self.assertTrue(result.success)
        self.assertEqual(result.product_info.name, "Test Product")
        self.assertEqual(result.product_info.price, 29.99)
        self.assertEqual(result.best_parser, "TestParser")
        self.assertEqual(len(result.attempts), 1)
        self.assertTrue(result.attempts[0].success)
    
    def test_parse_product_success_multiple_parsers(self):
        """Test parsing with multiple parsers, best one wins."""
        # Low confidence parser
        parser1 = MockParser("LowConfidence", confidence=0.5, 
                           product_info=ProductInfo(name="Low", price=10.0))
        # High confidence parser
        parser2 = MockParser("HighConfidence", confidence=0.9,
                           product_info=ProductInfo(name="High", price=20.0))
        
        self.service.register_parser(parser1)
        self.service.register_parser(parser2)
        
        result = self.service.parse_product("https://example.com/product", self.page_content)
        
        self.assertTrue(result.success)
        self.assertEqual(result.product_info.name, "High")
        self.assertEqual(result.best_parser, "HighConfidence")
        self.assertEqual(result.confidence_score, 0.9)
        self.assertEqual(len(result.attempts), 2)
    
    def test_parse_product_early_stop_high_confidence(self):
        """Test that parsing stops early with high confidence result."""
        # High confidence parser (should stop here)
        parser1 = MockParser("HighConfidence", confidence=0.95,
                           product_info=ProductInfo(name="High", price=20.0))
        # Another parser that shouldn't be called
        parser2 = MockParser("SecondParser", confidence=0.8)
        
        self.service.register_parser(parser1)
        self.service.register_parser(parser2)
        
        result = self.service.parse_product("https://example.com/product", self.page_content)
        
        self.assertTrue(result.success)
        self.assertEqual(result.best_parser, "HighConfidence")
        # Should only have one attempt due to early stopping
        self.assertEqual(len(result.attempts), 1)
    
    def test_parse_product_parser_cannot_parse(self):
        """Test behavior when parser cannot parse content."""
        parser = MockParser("TestParser", can_parse_result=False)
        self.service.register_parser(parser)
        
        result = self.service.parse_product("https://example.com/product", self.page_content)
        
        self.assertFalse(result.success)
        self.assertIn("All parsing attempts failed", result.error_message)
        self.assertEqual(len(result.attempts), 0)  # No attempts made
    
    def test_parse_product_all_parsers_fail(self):
        """Test behavior when all parsers fail."""
        parser1 = MockParser("Parser1", parse_success=False)
        parser2 = MockParser("Parser2", parse_success=False)
        
        self.service.register_parser(parser1)
        self.service.register_parser(parser2)
        
        result = self.service.parse_product("https://example.com/product", self.page_content)
        
        self.assertFalse(result.success)
        self.assertIn("All parsing attempts failed", result.error_message)
        self.assertEqual(len(result.attempts), 2)
        self.assertFalse(result.attempts[0].success)
        self.assertFalse(result.attempts[1].success)
    
    def test_parse_product_invalid_content(self):
        """Test parsing with invalid content."""
        parser = MockParser("TestParser")
        self.service.register_parser(parser)
        
        # Test with None content
        result = self.service.parse_product("https://example.com/product", None)
        self.assertFalse(result.success)
        self.assertIn("Invalid or empty page content", result.error_message)
        
        # Test with empty HTML
        empty_content = PageContent("https://example.com", "", 200, {})
        result = self.service.parse_product("https://example.com/product", empty_content)
        self.assertFalse(result.success)
        self.assertIn("Invalid or empty page content", result.error_message)
    
    def test_parse_product_parser_exception(self):
        """Test handling of parser exceptions."""
        parser = MockParser("TestParser")
        # Mock the parse method to raise an exception
        parser.parse = Mock(side_effect=Exception("Parser crashed"))
        
        self.service.register_parser(parser)
        
        result = self.service.parse_product("https://example.com/product", self.page_content)
        
        self.assertFalse(result.success)
        self.assertEqual(len(result.attempts), 1)
        self.assertFalse(result.attempts[0].success)
        self.assertIn("Unexpected error in parser TestParser", result.attempts[0].error_message)
    
    def test_validate_product_info_valid(self):
        """Test validation of valid product info."""
        valid_products = [
            ProductInfo(name="Valid Product", price=29.99),
            ProductInfo(name="Another Product", price=100.0, currency="USD"),
            ProductInfo(name="Product with Image", price=50.0, image_url="https://example.com/image.jpg"),
        ]
        
        for product in valid_products:
            with self.subTest(product=product):
                self.assertTrue(self.service._validate_product_info(product))
    
    def test_validate_product_info_invalid(self):
        """Test validation of invalid product info."""
        invalid_products = [
            None,
            ProductInfo(),  # No name or price
            ProductInfo(name="", price=29.99),  # Empty name
            ProductInfo(name="A", price=29.99),  # Name too short
            ProductInfo(name="123", price=29.99),  # Name with no letters
            ProductInfo(name="Valid Product", price=0),  # Zero price
            ProductInfo(name="Valid Product", price=-10),  # Negative price
            ProductInfo(name="Valid Product", price=2000000),  # Price too high
        ]
        
        for product in invalid_products:
            with self.subTest(product=product):
                self.assertFalse(self.service._validate_product_info(product))
    
    def test_sanitize_product_info(self):
        """Test sanitization of product info."""
        # Test name cleaning
        product = ProductInfo(
            name="  Product   with   extra   spaces  ",
            price=29.99,
            description="  Description   with   spaces  ",
            currency="  usd  ",
            availability="  In Stock  "
        )
        
        sanitized = self.service._sanitize_product_info(product)
        
        self.assertEqual(sanitized.name, "Product with extra spaces")
        self.assertEqual(sanitized.description, "Description with spaces")
        self.assertEqual(sanitized.currency, "USD")
        self.assertEqual(sanitized.availability, "In Stock")
    
    def test_sanitize_product_info_long_content(self):
        """Test sanitization of overly long content."""
        long_name = "A" * 250
        long_description = "B" * 1100
        
        product = ProductInfo(
            name=long_name,
            price=29.99,
            description=long_description
        )
        
        sanitized = self.service._sanitize_product_info(product)
        
        self.assertEqual(len(sanitized.name), 203)  # 200 + "..."
        self.assertTrue(sanitized.name.endswith("..."))
        self.assertEqual(len(sanitized.description), 1003)  # 1000 + "..."
        self.assertTrue(sanitized.description.endswith("..."))
    
    def test_sanitize_product_info_invalid_image_url(self):
        """Test sanitization of invalid image URLs."""
        product = ProductInfo(
            name="Test Product",
            price=29.99,
            image_url="not-a-valid-url"
        )
        
        sanitized = self.service._sanitize_product_info(product)
        
        self.assertIsNone(sanitized.image_url)
    
    def test_get_parser_stats(self):
        """Test getting parser statistics."""
        parser1 = MockParser("Parser1")
        parser2 = MockParser("Parser2")
        
        self.service.register_parser(parser1)
        self.service.register_parser(parser2)
        
        stats = self.service.get_parser_stats()
        
        self.assertEqual(stats['total_parsers'], 2)
        self.assertEqual(stats['parser_names'], ['Parser1', 'Parser2'])
        self.assertFalse(stats['ai_enabled'])  # No AI parser registered
    
    def test_test_parsers(self):
        """Test the test_parsers method."""
        parser1 = MockParser("CanParse", can_parse_result=True)
        parser2 = MockParser("CannotParse", can_parse_result=False)
        
        self.service.register_parser(parser1)
        self.service.register_parser(parser2)
        
        results = self.service.test_parsers(self.page_content)
        
        self.assertTrue(results['CanParse'])
        self.assertFalse(results['CannotParse'])
    
    def test_test_parsers_with_exception(self):
        """Test test_parsers method with parser exception."""
        parser = MockParser("TestParser")
        parser.can_parse = Mock(side_effect=Exception("Parser error"))
        
        self.service.register_parser(parser)
        
        results = self.service.test_parsers(self.page_content)
        
        self.assertFalse(results['TestParser'])
    
    @patch('src.services.parser_service.StructuredDataParser')
    @patch('src.services.parser_service.HtmlCssParser')
    def test_default_parser_registration(self, mock_html_parser, mock_structured_parser):
        """Test that default parsers are registered correctly."""
        # Create a new service with default parsers
        service = ParserService(enable_ai_parsing=False)
        
        # Should have registered structured data and HTML parsers
        self.assertEqual(len(service.parsers), 2)
        mock_structured_parser.assert_called_once()
        mock_html_parser.assert_called_once()
    
    @patch('src.services.parser_service.AIParser')
    @patch('src.services.parser_service.StructuredDataParser')
    @patch('src.services.parser_service.HtmlCssParser')
    def test_default_parser_registration_with_ai(self, mock_html_parser, 
                                                mock_structured_parser, mock_ai_parser):
        """Test that AI parser is registered when enabled."""
        # Create a new service with AI enabled
        service = ParserService(ai_api_key="test-key", enable_ai_parsing=True)
        
        # Should have registered all three parsers
        self.assertEqual(len(service.parsers), 3)
        mock_structured_parser.assert_called_once()
        mock_ai_parser.assert_called_once_with("test-key", None, enabled=True)
        mock_html_parser.assert_called_once()


if __name__ == '__main__':
    unittest.main()