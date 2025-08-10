"""
Tests for product parsing functionality.
"""
import unittest
from unittest.mock import Mock, patch
import json

from src.models.web_scraping import PageContent, ProductInfo
from src.parsers.product_parser import ProductParser, ParsingResult
from src.parsers.html_parser import HtmlCssParser
from src.parsers.structured_data_parser import StructuredDataParser
from src.parsers.ai_parser import AIParser


class TestProductParser(unittest.TestCase):
    """Test cases for base ProductParser class."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create a concrete implementation for testing
        class TestParser(ProductParser):
            def can_parse(self, content):
                return True
            
            def parse(self, content):
                return ParsingResult.success_result(
                    ProductInfo(name="Test", price=10.0),
                    self.name
                )
        
        self.parser = TestParser("TestParser")
    
    def test_clean_text(self):
        """Test text cleaning functionality."""
        test_cases = [
            ("  Hello   World  ", "Hello World"),
            ("Product\n\tName", "Product Name"),
            ("Price: $29.99", "Price: $29.99"),
            ("", ""),
            (None, ""),
        ]
        
        for input_text, expected in test_cases:
            with self.subTest(input_text=input_text):
                result = self.parser._clean_text(input_text)
                self.assertEqual(result, expected)
    
    def test_extract_price_from_text(self):
        """Test price extraction from text."""
        test_cases = [
            ("$29.99", 29.99),
            ("€1,234.56", 1234.56),
            ("£99", 99.0),
            ("Price: 45.00", 45.0),
            ("29.99$", 29.99),
            ("1.234,56€", 1234.56),  # European format
            ("123,45", 123.45),  # European decimal
            ("No price here", None),
            ("", None),
            (None, None),
        ]
        
        for input_text, expected in test_cases:
            with self.subTest(input_text=input_text):
                result = self.parser._extract_price_from_text(input_text)
                self.assertEqual(result, expected)
    
    def test_extract_currency_from_text(self):
        """Test currency extraction from text."""
        test_cases = [
            ("$29.99", "USD"),
            ("€123.45", "EUR"),
            ("£99.00", "GBP"),
            ("¥1000", "JPY"),
            ("Price in USD", "USD"),
            ("29.99 EUR", "EUR"),
            ("No currency", None),
            ("", None),
            (None, None),
        ]
        
        for input_text, expected in test_cases:
            with self.subTest(input_text=input_text):
                result = self.parser._extract_currency_from_text(input_text)
                self.assertEqual(result, expected)


class TestParsingResult(unittest.TestCase):
    """Test cases for ParsingResult class."""
    
    def test_success_result_creation(self):
        """Test creating a successful parsing result."""
        product_info = ProductInfo(name="Test Product", price=29.99)
        result = ParsingResult.success_result(product_info, "TestParser", 0.8)
        
        self.assertTrue(result.success)
        self.assertEqual(result.product_info, product_info)
        self.assertEqual(result.parser_name, "TestParser")
        self.assertEqual(result.confidence_score, 0.8)
        self.assertIsNone(result.error_message)
    
    def test_error_result_creation(self):
        """Test creating an error parsing result."""
        error_msg = "Parsing failed"
        result = ParsingResult.error_result(error_msg, "TestParser")
        
        self.assertFalse(result.success)
        self.assertIsNone(result.product_info)
        self.assertEqual(result.error_message, error_msg)
        self.assertEqual(result.parser_name, "TestParser")
        self.assertEqual(result.confidence_score, 0.0)


class TestHtmlCssParser(unittest.TestCase):
    """Test cases for HtmlCssParser."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.parser = HtmlCssParser()
        
        # Sample HTML for testing
        self.sample_html = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Test Product - Shop</title>
            <meta name="description" content="A great test product">
        </head>
        <body>
            <div class="product-container">
                <h1 class="product-title">Awesome Test Product</h1>
                <div class="price">$29.99</div>
                <img class="product-image" src="/images/product.jpg" alt="Product">
                <div class="availability">In Stock</div>
                <div class="product-description">This is a great product for testing.</div>
            </div>
        </body>
        </html>
        """
        
        self.page_content = PageContent(
            url="https://example.com/product",
            html=self.sample_html,
            status_code=200,
            headers={}
        )
    
    def test_can_parse_product_page(self):
        """Test detection of product pages."""
        self.assertTrue(self.parser.can_parse(self.page_content))
    
    def test_can_parse_non_product_page(self):
        """Test detection of non-product pages."""
        non_product_html = """
        <html>
        <body>
            <h1>About Us</h1>
            <p>This is not a product page.</p>
        </body>
        </html>
        """
        
        non_product_content = PageContent(
            url="https://example.com/about",
            html=non_product_html,
            status_code=200,
            headers={}
        )
        
        self.assertFalse(self.parser.can_parse(non_product_content))
    
    def test_parse_success(self):
        """Test successful parsing of product information."""
        result = self.parser.parse(self.page_content)
        
        self.assertTrue(result.success)
        self.assertIsNotNone(result.product_info)
        self.assertEqual(result.product_info.name, "Awesome Test Product")
        self.assertEqual(result.product_info.price, 29.99)
        self.assertEqual(result.product_info.image_url, "https://example.com/images/product.jpg")
        self.assertEqual(result.product_info.availability, "In Stock")
        self.assertGreater(result.confidence_score, 0.5)
    
    def test_parse_minimal_product(self):
        """Test parsing with minimal product information."""
        minimal_html = """
        <html>
        <body>
            <h1>Simple Product</h1>
            <span class="price">$19.99</span>
        </body>
        </html>
        """
        
        minimal_content = PageContent(
            url="https://example.com/simple",
            html=minimal_html,
            status_code=200,
            headers={}
        )
        
        result = self.parser.parse(minimal_content)
        
        self.assertTrue(result.success)
        self.assertEqual(result.product_info.name, "Simple Product")
        self.assertEqual(result.product_info.price, 19.99)
    
    def test_parse_no_price(self):
        """Test parsing failure when no price is found."""
        no_price_html = """
        <html>
        <body>
            <h1>Product Without Price</h1>
            <p>This product has no price.</p>
        </body>
        </html>
        """
        
        no_price_content = PageContent(
            url="https://example.com/noprice",
            html=no_price_html,
            status_code=200,
            headers={}
        )
        
        result = self.parser.parse(no_price_content)
        
        self.assertFalse(result.success)
        self.assertIn("minimum required", result.error_message)


class TestStructuredDataParser(unittest.TestCase):
    """Test cases for StructuredDataParser."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.parser = StructuredDataParser()
        
        # Sample JSON-LD structured data
        self.json_ld_html = """
        <html>
        <head>
            <script type="application/ld+json">
            {
                "@context": "https://schema.org/",
                "@type": "Product",
                "name": "Structured Data Product",
                "image": "/images/structured-product.jpg",
                "description": "A product with structured data",
                "offers": {
                    "@type": "Offer",
                    "price": "39.99",
                    "priceCurrency": "USD",
                    "availability": "https://schema.org/InStock"
                }
            }
            </script>
        </head>
        <body>
            <h1>Product Page</h1>
        </body>
        </html>
        """
        
        # Sample microdata
        self.microdata_html = """
        <html>
        <body>
            <div itemscope itemtype="https://schema.org/Product">
                <h1 itemprop="name">Microdata Product</h1>
                <img itemprop="image" src="/images/micro-product.jpg" alt="Product">
                <div itemprop="offers" itemscope itemtype="https://schema.org/Offer">
                    <span itemprop="price" content="49.99">$49.99</span>
                    <meta itemprop="priceCurrency" content="USD">
                    <link itemprop="availability" href="https://schema.org/InStock">
                </div>
            </div>
        </body>
        </html>
        """
    
    def test_can_parse_json_ld(self):
        """Test detection of JSON-LD structured data."""
        content = PageContent(
            url="https://example.com/product",
            html=self.json_ld_html,
            status_code=200,
            headers={}
        )
        
        self.assertTrue(self.parser.can_parse(content))
    
    def test_can_parse_microdata(self):
        """Test detection of microdata."""
        content = PageContent(
            url="https://example.com/product",
            html=self.microdata_html,
            status_code=200,
            headers={}
        )
        
        self.assertTrue(self.parser.can_parse(content))
    
    def test_parse_json_ld_success(self):
        """Test successful parsing of JSON-LD data."""
        content = PageContent(
            url="https://example.com/product",
            html=self.json_ld_html,
            status_code=200,
            headers={}
        )
        
        result = self.parser.parse(content)
        
        self.assertTrue(result.success)
        self.assertEqual(result.product_info.name, "Structured Data Product")
        self.assertEqual(result.product_info.price, 39.99)
        self.assertEqual(result.product_info.currency, "USD")
        self.assertEqual(result.product_info.image_url, "https://example.com/images/structured-product.jpg")
        self.assertEqual(result.product_info.availability, "In Stock")
        self.assertEqual(result.confidence_score, 0.9)
    
    def test_parse_microdata_success(self):
        """Test successful parsing of microdata."""
        content = PageContent(
            url="https://example.com/product",
            html=self.microdata_html,
            status_code=200,
            headers={}
        )
        
        result = self.parser.parse(content)
        
        self.assertTrue(result.success)
        self.assertEqual(result.product_info.name, "Microdata Product")
        self.assertEqual(result.product_info.price, 49.99)
        self.assertEqual(result.product_info.currency, "USD")
        self.assertEqual(result.product_info.image_url, "https://example.com/images/micro-product.jpg")
    
    def test_parse_no_structured_data(self):
        """Test parsing failure when no structured data is found."""
        no_data_html = """
        <html>
        <body>
            <h1>Regular Page</h1>
            <p>No structured data here.</p>
        </body>
        </html>
        """
        
        content = PageContent(
            url="https://example.com/regular",
            html=no_data_html,
            status_code=200,
            headers={}
        )
        
        result = self.parser.parse(content)
        
        self.assertFalse(result.success)
        self.assertIn("No valid product structured data", result.error_message)


class TestAIParser(unittest.TestCase):
    """Test cases for AIParser."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.parser = AIParser(api_key="test-key", enabled=True)
        
        self.sample_html = """
        <html>
        <body>
            <h1>AI Test Product</h1>
            <div class="price">$59.99</div>
            <img src="/images/ai-product.jpg" alt="AI Product">
        </body>
        </html>
        """
        
        self.page_content = PageContent(
            url="https://example.com/ai-product",
            html=self.sample_html,
            status_code=200,
            headers={}
        )
    
    def test_can_parse_when_enabled(self):
        """Test that parser can parse when enabled and configured."""
        self.assertTrue(self.parser.can_parse(self.page_content))
    
    def test_cannot_parse_when_disabled(self):
        """Test that parser cannot parse when disabled."""
        disabled_parser = AIParser(enabled=False)
        self.assertFalse(disabled_parser.can_parse(self.page_content))
    
    def test_cannot_parse_without_api_key(self):
        """Test that parser cannot parse without API key."""
        no_key_parser = AIParser(api_key=None)
        self.assertFalse(no_key_parser.can_parse(self.page_content))
    
    @patch('src.parsers.ai_parser.requests.post')
    def test_parse_success(self, mock_post):
        """Test successful AI parsing."""
        # Mock AI API response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'choices': [{
                'message': {
                    'content': json.dumps({
                        'name': 'AI Test Product',
                        'price': 59.99,
                        'currency': 'USD',
                        'image_url': '/images/ai-product.jpg',
                        'availability': 'In Stock',
                        'description': 'A product parsed by AI'
                    })
                }
            }]
        }
        mock_post.return_value = mock_response
        
        result = self.parser.parse(self.page_content)
        
        self.assertTrue(result.success)
        self.assertEqual(result.product_info.name, "AI Test Product")
        self.assertEqual(result.product_info.price, 59.99)
        self.assertEqual(result.product_info.currency, "USD")
        self.assertEqual(result.product_info.image_url, "https://example.com/images/ai-product.jpg")
        self.assertEqual(result.confidence_score, 0.8)
    
    @patch('src.parsers.ai_parser.requests.post')
    def test_parse_api_error(self, mock_post):
        """Test handling of AI API errors."""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_post.return_value = mock_response
        
        result = self.parser.parse(self.page_content)
        
        self.assertFalse(result.success)
        self.assertIn("AI API call failed", result.error_message)
    
    def test_parse_disabled(self):
        """Test parsing when AI is disabled."""
        disabled_parser = AIParser(enabled=False)
        result = disabled_parser.parse(self.page_content)
        
        self.assertFalse(result.success)
        self.assertIn("AI parsing is disabled", result.error_message)
    
    def test_clean_html_for_ai(self):
        """Test HTML cleaning for AI processing."""
        messy_html = """
        <html>
        <head>
            <script>alert('test');</script>
            <style>body { color: red; }</style>
        </head>
        <body>
            <main>
                <h1>Product Name</h1>
                <div class="price">$29.99</div>
            </main>
            <!-- This is a comment -->
        </body>
        </html>
        """
        
        cleaned = self.parser._clean_html_for_ai(messy_html)
        
        # Should remove scripts and styles
        self.assertNotIn('<script>', cleaned)
        self.assertNotIn('<style>', cleaned)
        self.assertNotIn('alert', cleaned)
        
        # Should keep main content
        self.assertIn('Product Name', cleaned)
        self.assertIn('$29.99', cleaned)


if __name__ == '__main__':
    unittest.main()