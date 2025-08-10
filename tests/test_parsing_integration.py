"""
Integration tests for the complete parsing workflow.
"""
import unittest
from unittest.mock import Mock, patch

from src.models.web_scraping import PageContent
from src.services.parser_service import ParserService
from src.services.web_scraping_service import WebScrapingService


class TestParsingIntegration(unittest.TestCase):
    """Integration tests for the complete parsing workflow."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.parser_service = ParserService(enable_ai_parsing=False)  # Disable AI for testing
        self.web_scraping_service = WebScrapingService(timeout=10, max_retries=1)
    
    def test_parse_structured_data_product(self):
        """Test parsing a product page with structured data."""
        html_content = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Awesome Product - Shop</title>
            <script type="application/ld+json">
            {
                "@context": "https://schema.org/",
                "@type": "Product",
                "name": "Awesome Structured Product",
                "image": "https://example.com/images/product.jpg",
                "description": "A great product with structured data",
                "offers": {
                    "@type": "Offer",
                    "price": "49.99",
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
        
        page_content = PageContent(
            url="https://example.com/product",
            html=html_content,
            status_code=200,
            headers={"Content-Type": "text/html"}
        )
        
        result = self.parser_service.parse_product("https://example.com/product", page_content)
        
        self.assertTrue(result.success)
        self.assertEqual(result.product_info.name, "Awesome Structured Product")
        self.assertEqual(result.product_info.price, 49.99)
        self.assertEqual(result.product_info.currency, "USD")
        self.assertEqual(result.product_info.image_url, "https://example.com/images/product.jpg")
        self.assertEqual(result.product_info.availability, "In Stock")
        self.assertEqual(result.best_parser, "StructuredDataParser")
        self.assertGreater(result.confidence_score, 0.8)
    
    def test_parse_html_product_fallback(self):
        """Test parsing a product page with HTML/CSS selectors as fallback."""
        html_content = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>HTML Product - Shop</title>
        </head>
        <body>
            <div class="product-container">
                <h1 class="product-title">HTML Parsed Product</h1>
                <div class="price">$39.99</div>
                <img class="product-image" src="/images/html-product.jpg" alt="Product">
                <div class="availability">In Stock</div>
                <div class="product-description">A product parsed from HTML.</div>
            </div>
        </body>
        </html>
        """
        
        page_content = PageContent(
            url="https://example.com/html-product",
            html=html_content,
            status_code=200,
            headers={"Content-Type": "text/html"}
        )
        
        result = self.parser_service.parse_product("https://example.com/html-product", page_content)
        
        self.assertTrue(result.success)
        self.assertEqual(result.product_info.name, "HTML Parsed Product")
        self.assertEqual(result.product_info.price, 39.99)
        self.assertEqual(result.product_info.image_url, "https://example.com/images/html-product.jpg")
        self.assertEqual(result.product_info.availability, "In Stock")
        self.assertEqual(result.best_parser, "HtmlCssParser")
    
    def test_parse_microdata_product(self):
        """Test parsing a product page with microdata."""
        html_content = """
        <!DOCTYPE html>
        <html>
        <body>
            <div itemscope itemtype="https://schema.org/Product">
                <h1 itemprop="name">Microdata Product</h1>
                <img itemprop="image" src="/images/micro-product.jpg" alt="Product">
                <p itemprop="description">A product with microdata markup.</p>
                <div itemprop="offers" itemscope itemtype="https://schema.org/Offer">
                    <span itemprop="price" content="59.99">$59.99</span>
                    <meta itemprop="priceCurrency" content="USD">
                    <link itemprop="availability" href="https://schema.org/InStock">
                </div>
            </div>
        </body>
        </html>
        """
        
        page_content = PageContent(
            url="https://example.com/microdata-product",
            html=html_content,
            status_code=200,
            headers={"Content-Type": "text/html"}
        )
        
        result = self.parser_service.parse_product("https://example.com/microdata-product", page_content)
        
        self.assertTrue(result.success)
        self.assertEqual(result.product_info.name, "Microdata Product")
        self.assertEqual(result.product_info.price, 59.99)
        self.assertEqual(result.product_info.currency, "USD")
        self.assertEqual(result.product_info.image_url, "https://example.com/images/micro-product.jpg")
        self.assertEqual(result.best_parser, "StructuredDataParser")
    
    def test_parse_multiple_strategies_best_wins(self):
        """Test that the best parsing strategy wins when multiple can parse."""
        # HTML with both structured data and HTML elements
        html_content = """
        <!DOCTYPE html>
        <html>
        <head>
            <script type="application/ld+json">
            {
                "@context": "https://schema.org/",
                "@type": "Product",
                "name": "Structured Data Winner",
                "offers": {
                    "@type": "Offer",
                    "price": "99.99",
                    "priceCurrency": "USD"
                }
            }
            </script>
        </head>
        <body>
            <div class="product-container">
                <h1 class="product-title">HTML Title</h1>
                <div class="price">$89.99</div>
            </div>
        </body>
        </html>
        """
        
        page_content = PageContent(
            url="https://example.com/multi-strategy",
            html=html_content,
            status_code=200,
            headers={"Content-Type": "text/html"}
        )
        
        result = self.parser_service.parse_product("https://example.com/multi-strategy", page_content)
        
        self.assertTrue(result.success)
        # Structured data should win due to higher confidence
        self.assertEqual(result.product_info.name, "Structured Data Winner")
        self.assertEqual(result.product_info.price, 99.99)
        self.assertEqual(result.best_parser, "StructuredDataParser")
        self.assertGreater(result.confidence_score, 0.8)
    
    def test_parse_no_product_data(self):
        """Test parsing a page with no product data."""
        html_content = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>About Us - Company</title>
        </head>
        <body>
            <h1>About Our Company</h1>
            <p>We are a great company that does things.</p>
            <p>Contact us at info@company.com</p>
        </body>
        </html>
        """
        
        page_content = PageContent(
            url="https://example.com/about",
            html=html_content,
            status_code=200,
            headers={"Content-Type": "text/html"}
        )
        
        result = self.parser_service.parse_product("https://example.com/about", page_content)
        
        self.assertFalse(result.success)
        self.assertIn("All parsing attempts failed", result.error_message)
        # Should have attempted with parsers that can't parse this content
        self.assertEqual(len(result.attempts), 0)  # No parsers can parse this
    
    def test_parse_invalid_product_data(self):
        """Test parsing a page with invalid product data."""
        html_content = """
        <!DOCTYPE html>
        <html>
        <body>
            <div class="product-container">
                <h1 class="product-title">X</h1>  <!-- Name too short -->
                <div class="price">$0</div>  <!-- Invalid price -->
            </div>
        </body>
        </html>
        """
        
        page_content = PageContent(
            url="https://example.com/invalid-product",
            html=html_content,
            status_code=200,
            headers={"Content-Type": "text/html"}
        )
        
        result = self.parser_service.parse_product("https://example.com/invalid-product", page_content)
        
        self.assertFalse(result.success)
        # Should have attempted parsing but validation failed
        self.assertGreater(len(result.attempts), 0)
    
    def test_parser_service_stats(self):
        """Test getting parser service statistics."""
        stats = self.parser_service.get_parser_stats()
        
        self.assertGreater(stats['total_parsers'], 0)
        self.assertIn('StructuredDataParser', stats['parser_names'])
        self.assertIn('HtmlCssParser', stats['parser_names'])
        self.assertFalse(stats['ai_enabled'])  # AI disabled for testing
    
    def test_parser_capability_testing(self):
        """Test the parser capability testing functionality."""
        # Structured data content
        structured_html = """
        <html>
        <head>
            <script type="application/ld+json">
            {"@type": "Product", "name": "Test"}
            </script>
        </head>
        </html>
        """
        
        structured_content = PageContent(
            url="https://example.com/structured",
            html=structured_html,
            status_code=200,
            headers={}
        )
        
        capabilities = self.parser_service.test_parsers(structured_content)
        
        self.assertTrue(capabilities['StructuredDataParser'])
        # HTML parser might also be able to parse this
        self.assertIn('HtmlCssParser', capabilities)
    
    @patch('src.services.web_scraping_service.requests.Session.get')
    def test_end_to_end_workflow(self, mock_get):
        """Test the complete end-to-end workflow from URL to parsed product."""
        # Mock the HTTP response
        html_content = """
        <!DOCTYPE html>
        <html>
        <head>
            <script type="application/ld+json">
            {
                "@context": "https://schema.org/",
                "@type": "Product",
                "name": "End-to-End Product",
                "offers": {
                    "@type": "Offer",
                    "price": "79.99",
                    "priceCurrency": "USD"
                }
            }
            </script>
        </head>
        <body>
            <h1>Product Page</h1>
        </body>
        </html>
        """
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = html_content
        mock_response.url = "https://example.com/end-to-end"
        mock_response.headers = {"Content-Type": "text/html"}
        mock_response.encoding = "utf-8"
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        # Step 1: Scrape the page
        scraping_result = self.web_scraping_service.fetch_page_content("https://example.com/end-to-end")
        
        self.assertTrue(scraping_result.success)
        self.assertIsNotNone(scraping_result.page_content)
        
        # Step 2: Parse the product information
        parsing_result = self.parser_service.parse_product(
            "https://example.com/end-to-end", 
            scraping_result.page_content
        )
        
        self.assertTrue(parsing_result.success)
        self.assertEqual(parsing_result.product_info.name, "End-to-End Product")
        self.assertEqual(parsing_result.product_info.price, 79.99)
        self.assertEqual(parsing_result.product_info.currency, "USD")
        self.assertEqual(parsing_result.best_parser, "StructuredDataParser")


if __name__ == '__main__':
    unittest.main()