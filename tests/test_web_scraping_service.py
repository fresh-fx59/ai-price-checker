"""
Tests for web scraping service functionality.
"""
import unittest
from unittest.mock import Mock, patch, MagicMock
import requests
from datetime import datetime

from src.services.web_scraping_service import WebScrapingService
from src.models.web_scraping import PageContent, ScrapingResult


class TestWebScrapingService(unittest.TestCase):
    """Test cases for WebScrapingService."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.service = WebScrapingService(timeout=10, max_retries=2)
        
        # Sample HTML content for testing
        self.sample_html = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Test Product Page</title>
            <meta name="description" content="A test product description">
        </head>
        <body>
            <h1>Test Product</h1>
            <div class="price">$29.99</div>
            <img src="/images/product1.jpg" alt="Product 1">
            <img src="https://example.com/images/product2.jpg" alt="Product 2">
            <img data-src="/images/lazy-product.jpg" alt="Lazy Product">
        </body>
        </html>
        """
    
    def test_init_default_values(self):
        """Test service initialization with default values."""
        service = WebScrapingService()
        self.assertEqual(service.timeout, 30)
        self.assertEqual(service.max_retries, 3)
        self.assertEqual(service.backoff_factor, 1.0)
        self.assertIsNotNone(service.user_agent)
        self.assertIsNotNone(service.session)
    
    def test_init_custom_values(self):
        """Test service initialization with custom values."""
        custom_ua = "Custom User Agent"
        service = WebScrapingService(
            timeout=15,
            max_retries=5,
            backoff_factor=2.0,
            user_agent=custom_ua
        )
        self.assertEqual(service.timeout, 15)
        self.assertEqual(service.max_retries, 5)
        self.assertEqual(service.backoff_factor, 2.0)
        self.assertEqual(service.user_agent, custom_ua)
    
    def test_is_valid_url_valid_urls(self):
        """Test URL validation with valid URLs."""
        valid_urls = [
            "https://example.com",
            "http://example.com",
            "https://example.com/path",
            "https://example.com/path?query=value",
            "https://subdomain.example.com",
        ]
        
        for url in valid_urls:
            with self.subTest(url=url):
                self.assertTrue(self.service._is_valid_url(url))
    
    def test_is_valid_url_invalid_urls(self):
        """Test URL validation with invalid URLs."""
        invalid_urls = [
            "",
            "not-a-url",
            "ftp://example.com",  # Unsupported scheme
            "//example.com",  # Missing scheme
            "https://",  # Missing netloc
        ]
        
        for url in invalid_urls:
            with self.subTest(url=url):
                self.assertFalse(self.service._is_valid_url(url))
    
    @patch('src.services.web_scraping_service.requests.Session.get')
    def test_fetch_page_content_success(self, mock_get):
        """Test successful page content fetching."""
        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = self.sample_html
        mock_response.url = "https://example.com"
        mock_response.headers = {"Content-Type": "text/html"}
        mock_response.encoding = "utf-8"
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        result = self.service.fetch_page_content("https://example.com")
        
        self.assertTrue(result.success)
        self.assertIsNotNone(result.page_content)
        self.assertEqual(result.page_content.url, "https://example.com")
        self.assertEqual(result.page_content.html, self.sample_html)
        self.assertEqual(result.page_content.status_code, 200)
        self.assertIsNone(result.error_message)
    
    def test_fetch_page_content_invalid_url(self):
        """Test fetching with invalid URL."""
        result = self.service.fetch_page_content("invalid-url")
        
        self.assertFalse(result.success)
        self.assertIsNone(result.page_content)
        self.assertIn("Invalid URL format", result.error_message)
    
    @patch('src.services.web_scraping_service.requests.Session.get')
    def test_fetch_page_content_timeout(self, mock_get):
        """Test handling of request timeout."""
        mock_get.side_effect = requests.exceptions.Timeout("Request timed out")
        
        result = self.service.fetch_page_content("https://example.com")
        
        self.assertFalse(result.success)
        self.assertIsNone(result.page_content)
        self.assertIn("Request timeout", result.error_message)
        self.assertEqual(result.retry_count, self.service.max_retries + 1)
    
    @patch('src.services.web_scraping_service.requests.Session.get')
    def test_fetch_page_content_connection_error(self, mock_get):
        """Test handling of connection error."""
        mock_get.side_effect = requests.exceptions.ConnectionError("Connection failed")
        
        result = self.service.fetch_page_content("https://example.com")
        
        self.assertFalse(result.success)
        self.assertIsNone(result.page_content)
        self.assertIn("Connection error", result.error_message)
    
    @patch('src.services.web_scraping_service.requests.Session.get')
    def test_fetch_page_content_http_error_4xx(self, mock_get):
        """Test handling of 4xx HTTP errors (no retry)."""
        mock_response = Mock()
        mock_response.status_code = 404
        http_error = requests.exceptions.HTTPError("404 Not Found")
        http_error.response = mock_response
        mock_get.side_effect = http_error
        
        result = self.service.fetch_page_content("https://example.com")
        
        self.assertFalse(result.success)
        self.assertIsNone(result.page_content)
        self.assertIn("HTTP error 404", result.error_message)
        # Should not retry for 4xx errors
        self.assertEqual(result.retry_count, 1)
    
    @patch('src.services.web_scraping_service.requests.Session.get')
    def test_fetch_page_content_http_error_5xx(self, mock_get):
        """Test handling of 5xx HTTP errors (with retry)."""
        mock_response = Mock()
        mock_response.status_code = 500
        http_error = requests.exceptions.HTTPError("500 Internal Server Error")
        http_error.response = mock_response
        mock_get.side_effect = http_error
        
        result = self.service.fetch_page_content("https://example.com")
        
        self.assertFalse(result.success)
        self.assertIsNone(result.page_content)
        self.assertIn("HTTP error 500", result.error_message)
        # Should retry for 5xx errors
        self.assertEqual(result.retry_count, self.service.max_retries + 1)
    
    @patch('src.services.web_scraping_service.time.sleep')
    @patch('src.services.web_scraping_service.requests.Session.get')
    def test_fetch_page_content_retry_with_backoff(self, mock_get, mock_sleep):
        """Test retry mechanism with exponential backoff."""
        # First call fails, second succeeds
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = self.sample_html
        mock_response.url = "https://example.com"
        mock_response.headers = {}
        mock_response.encoding = "utf-8"
        mock_response.raise_for_status.return_value = None
        
        mock_get.side_effect = [
            requests.exceptions.Timeout("Timeout"),
            mock_response
        ]
        
        result = self.service.fetch_page_content("https://example.com")
        
        self.assertTrue(result.success)
        self.assertIsNotNone(result.page_content)
        # Should have slept once for retry
        mock_sleep.assert_called_once_with(self.service.backoff_factor)
    
    def test_extract_images_success(self):
        """Test successful image extraction."""
        page_content = PageContent(
            url="https://example.com",
            html=self.sample_html,
            status_code=200,
            headers={}
        )
        
        images = self.service.extract_images(page_content)
        
        expected_images = [
            "https://example.com/images/product1.jpg",
            "https://example.com/images/product2.jpg",
            "https://example.com/images/lazy-product.jpg"
        ]
        
        self.assertEqual(len(images), 3)
        for expected_img in expected_images:
            self.assertIn(expected_img, images)
    
    def test_extract_images_no_images(self):
        """Test image extraction with no images."""
        html_no_images = "<html><body><p>No images here</p></body></html>"
        page_content = PageContent(
            url="https://example.com",
            html=html_no_images,
            status_code=200,
            headers={}
        )
        
        images = self.service.extract_images(page_content)
        
        self.assertEqual(len(images), 0)
    
    def test_extract_images_duplicate_removal(self):
        """Test that duplicate images are removed."""
        html_with_duplicates = """
        <html><body>
            <img src="/image1.jpg">
            <img src="/image1.jpg">
            <img src="/image2.jpg">
        </body></html>
        """
        page_content = PageContent(
            url="https://example.com",
            html=html_with_duplicates,
            status_code=200,
            headers={}
        )
        
        images = self.service.extract_images(page_content)
        
        self.assertEqual(len(images), 2)
        self.assertIn("https://example.com/image1.jpg", images)
        self.assertIn("https://example.com/image2.jpg", images)
    
    def test_get_page_title_success(self):
        """Test successful page title extraction."""
        page_content = PageContent(
            url="https://example.com",
            html=self.sample_html,
            status_code=200,
            headers={}
        )
        
        title = self.service.get_page_title(page_content)
        
        self.assertEqual(title, "Test Product Page")
    
    def test_get_page_title_no_title(self):
        """Test page title extraction with no title tag."""
        html_no_title = "<html><body><p>No title</p></body></html>"
        page_content = PageContent(
            url="https://example.com",
            html=html_no_title,
            status_code=200,
            headers={}
        )
        
        title = self.service.get_page_title(page_content)
        
        self.assertIsNone(title)
    
    def test_get_meta_description_success(self):
        """Test successful meta description extraction."""
        page_content = PageContent(
            url="https://example.com",
            html=self.sample_html,
            status_code=200,
            headers={}
        )
        
        description = self.service.get_meta_description(page_content)
        
        self.assertEqual(description, "A test product description")
    
    def test_get_meta_description_no_meta(self):
        """Test meta description extraction with no meta tag."""
        html_no_meta = "<html><body><p>No meta</p></body></html>"
        page_content = PageContent(
            url="https://example.com",
            html=html_no_meta,
            status_code=200,
            headers={}
        )
        
        description = self.service.get_meta_description(page_content)
        
        self.assertIsNone(description)


class TestScrapingResult(unittest.TestCase):
    """Test cases for ScrapingResult class."""
    
    def test_success_result_creation(self):
        """Test creating a successful result."""
        page_content = PageContent(
            url="https://example.com",
            html="<html></html>",
            status_code=200,
            headers={}
        )
        
        result = ScrapingResult.success_result(page_content)
        
        self.assertTrue(result.success)
        self.assertEqual(result.page_content, page_content)
        self.assertIsNone(result.error_message)
        self.assertEqual(result.retry_count, 0)
    
    def test_error_result_creation(self):
        """Test creating an error result."""
        error_msg = "Test error"
        retry_count = 3
        
        result = ScrapingResult.error_result(error_msg, retry_count)
        
        self.assertFalse(result.success)
        self.assertIsNone(result.page_content)
        self.assertEqual(result.error_message, error_msg)
        self.assertEqual(result.retry_count, retry_count)


class TestPageContent(unittest.TestCase):
    """Test cases for PageContent class."""
    
    def test_page_content_creation(self):
        """Test PageContent creation and auto-timestamp."""
        before_creation = datetime.now()
        
        content = PageContent(
            url="https://example.com",
            html="<html></html>",
            status_code=200,
            headers={"Content-Type": "text/html"}
        )
        
        after_creation = datetime.now()
        
        self.assertEqual(content.url, "https://example.com")
        self.assertEqual(content.html, "<html></html>")
        self.assertEqual(content.status_code, 200)
        self.assertEqual(content.headers["Content-Type"], "text/html")
        self.assertIsNotNone(content.fetched_at)
        self.assertGreaterEqual(content.fetched_at, before_creation)
        self.assertLessEqual(content.fetched_at, after_creation)
    
    def test_page_content_with_custom_timestamp(self):
        """Test PageContent with custom timestamp."""
        custom_time = datetime(2023, 1, 1, 12, 0, 0)
        
        content = PageContent(
            url="https://example.com",
            html="<html></html>",
            status_code=200,
            headers={},
            fetched_at=custom_time
        )
        
        self.assertEqual(content.fetched_at, custom_time)


if __name__ == '__main__':
    unittest.main()