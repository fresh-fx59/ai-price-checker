"""
Price monitoring service for orchestrating price checks and comparison logic.
"""
import logging
import schedule
import time
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, Tuple
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
from enum import Enum

from ..models.database import Product, DatabaseManager
from ..models.web_scraping import ProductInfo
from .product_service import ProductService
from .parser_service import ParserService
from .web_scraping_service import WebScrapingService
from .email_service import EmailService, EmailDeliveryResult


class ErrorType(Enum):
    """Types of errors that can occur during monitoring."""
    NETWORK_ERROR = "network_error"
    PARSING_ERROR = "parsing_error"
    DATABASE_ERROR = "database_error"
    VALIDATION_ERROR = "validation_error"
    TIMEOUT_ERROR = "timeout_error"
    UNKNOWN_ERROR = "unknown_error"


@dataclass
class ErrorRecord:
    """Record of an error that occurred during monitoring."""
    product_id: int
    product_url: str
    error_type: ErrorType
    error_message: str
    timestamp: datetime
    retry_count: int = 0
    
    def __post_init__(self):
        if not isinstance(self.timestamp, datetime):
            self.timestamp = datetime.now()


@dataclass
class PriceCheckResult:
    """Result of a price check operation."""
    product_id: int
    product_name: str
    url: str
    success: bool
    old_price: Optional[float] = None
    new_price: Optional[float] = None
    price_dropped: bool = False
    is_new_lowest: bool = False
    error_message: Optional[str] = None
    check_timestamp: Optional[datetime] = None
    notification_sent: bool = False
    notification_error: Optional[str] = None
    
    def __post_init__(self):
        if self.check_timestamp is None:
            self.check_timestamp = datetime.now()
    
    @classmethod
    def success_result(cls, product_id: int, product_name: str, url: str, 
                      old_price: Optional[float], new_price: float, 
                      price_dropped: bool, is_new_lowest: bool,
                      notification_sent: bool = False, notification_error: Optional[str] = None) -> 'PriceCheckResult':
        """Create a successful price check result."""
        return cls(
            product_id=product_id,
            product_name=product_name,
            url=url,
            success=True,
            old_price=old_price,
            new_price=new_price,
            price_dropped=price_dropped,
            is_new_lowest=is_new_lowest,
            notification_sent=notification_sent,
            notification_error=notification_error
        )
    
    @classmethod
    def error_result(cls, product_id: int, product_name: str, url: str, 
                    error_message: str) -> 'PriceCheckResult':
        """Create an error price check result."""
        return cls(
            product_id=product_id,
            product_name=product_name,
            url=url,
            success=False,
            error_message=error_message
        )


@dataclass
class MonitoringStats:
    """Statistics from a monitoring run."""
    total_products: int
    successful_checks: int
    failed_checks: int
    price_drops_detected: int
    new_lowest_prices: int
    notifications_sent: int
    notification_failures: int
    start_time: datetime
    end_time: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    
    def complete(self):
        """Mark the monitoring run as complete."""
        self.end_time = datetime.now()
        if self.start_time:
            self.duration_seconds = (self.end_time - self.start_time).total_seconds()


class PriceMonitorService:
    """Service for orchestrating price checks and comparison logic."""
    
    def __init__(self, 
                 product_service: ProductService,
                 parser_service: ParserService,
                 web_scraping_service: WebScrapingService,
                 email_service: Optional[EmailService] = None,
                 max_concurrent_checks: int = 5,
                 check_timeout: int = 60,
                 max_retries: int = 3,
                 retry_delay: float = 1.0,
                 backoff_factor: float = 2.0):
        """
        Initialize the price monitor service.
        
        Args:
            product_service: Service for product operations
            parser_service: Service for parsing product information
            web_scraping_service: Service for web scraping
            email_service: Service for sending email notifications (optional)
            max_concurrent_checks: Maximum number of concurrent price checks
            check_timeout: Timeout for individual price checks in seconds
            max_retries: Maximum number of retry attempts for failed checks
            retry_delay: Initial delay between retries in seconds
            backoff_factor: Factor for exponential backoff between retries
        """
        self.product_service = product_service
        self.parser_service = parser_service
        self.web_scraping_service = web_scraping_service
        self.email_service = email_service
        self.max_concurrent_checks = max_concurrent_checks
        self.check_timeout = check_timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.backoff_factor = backoff_factor
        
        self.logger = logging.getLogger(__name__)
        self._scheduler_running = False
        self._scheduler_thread = None
        self._stop_scheduler = threading.Event()
        
        # Statistics tracking
        self._last_run_stats: Optional[MonitoringStats] = None
        self._total_runs = 0
        self._total_price_drops = 0
        
        # Error tracking
        self._error_history: List[ErrorRecord] = []
        self._failed_urls: Dict[str, datetime] = {}  # URL -> last failure time
        self._consecutive_failures: Dict[int, int] = {}  # product_id -> failure count
    
    def check_product(self, product_id: int) -> PriceCheckResult:
        """
        Check the price for a single product with retry logic.
        
        Args:
            product_id: ID of the product to check
            
        Returns:
            PriceCheckResult with the check outcome
        """
        # Get the product
        product = self.product_service.get_product(product_id)
        if not product:
            return PriceCheckResult.error_result(
                product_id, "Unknown", "", f"Product with ID {product_id} not found"
            )
        
        if not product.is_active:
            return PriceCheckResult.error_result(
                product_id, product.name, product.url, "Product is not active"
            )
        
        # Check if URL has been failing consistently
        if self._should_skip_url(product.url):
            error_msg = "URL temporarily disabled due to consecutive failures"
            self.logger.warning(f"Skipping {product.url}: {error_msg}")
            return PriceCheckResult.error_result(
                product_id, product.name, product.url, error_msg
            )
        
        self.logger.info(f"Checking price for product: {product.name} ({product.url})")
        
        # Attempt the check with retries
        for attempt in range(self.max_retries + 1):
            try:
                result = self._attempt_price_check(product, attempt)
                
                if result.success:
                    # Reset failure counters on success
                    self._reset_failure_tracking(product_id, product.url)
                    return result
                else:
                    # Record the failure
                    self._record_failure(product_id, product.url, result.error_message, attempt)
                    
                    # If this is not the last attempt, wait before retrying
                    if attempt < self.max_retries:
                        delay = self._calculate_retry_delay(attempt)
                        self.logger.info(f"Retrying {product.url} in {delay:.1f} seconds (attempt {attempt + 2}/{self.max_retries + 1})")
                        time.sleep(delay)
                    else:
                        # All attempts failed
                        self._handle_persistent_failure(product_id, product.url)
                        return result
                        
            except Exception as e:
                error_msg = f"Unexpected error during price check: {str(e)}"
                self.logger.error(f"Unexpected error checking {product.url} (attempt {attempt + 1}): {error_msg}")
                
                self._record_error(product_id, product.url, ErrorType.UNKNOWN_ERROR, error_msg, attempt)
                
                if attempt < self.max_retries:
                    delay = self._calculate_retry_delay(attempt)
                    time.sleep(delay)
                else:
                    return PriceCheckResult.error_result(
                        product_id, product.name, product.url, error_msg
                    )
        
        # This should never be reached, but just in case
        return PriceCheckResult.error_result(
            product_id, product.name, product.url, "All retry attempts exhausted"
        )
    
    def _attempt_price_check(self, product: Product, attempt_number: int) -> PriceCheckResult:
        """
        Attempt a single price check for a product.
        
        Args:
            product: Product to check
            attempt_number: Current attempt number (0-based)
            
        Returns:
            PriceCheckResult with the check outcome
        """
        try:
            # Fetch page content
            scraping_result = self.web_scraping_service.fetch_page_content(product.url)
            if not scraping_result.success:
                error_msg = f"Failed to fetch page: {scraping_result.error_message}"
                self.logger.error(f"Scraping failed for {product.url}: {error_msg}")
                self._record_error(product.id, product.url, ErrorType.NETWORK_ERROR, error_msg, attempt_number)
                return PriceCheckResult.error_result(
                    product.id, product.name, product.url, error_msg
                )
            
            # Parse product information
            parsing_result = self.parser_service.parse_product(product.url, scraping_result.page_content)
            if not parsing_result.success:
                error_msg = f"Failed to parse product info: {parsing_result.error_message}"
                self.logger.error(f"Parsing failed for {product.url}: {error_msg}")
                self._record_error(product.id, product.url, ErrorType.PARSING_ERROR, error_msg, attempt_number)
                return PriceCheckResult.error_result(
                    product.id, product.name, product.url, error_msg
                )
            
            # Extract new price
            product_info = parsing_result.product_info
            if not product_info or product_info.price is None:
                error_msg = "No price information found"
                self.logger.error(f"No price found for {product.url}")
                self._record_error(product.id, product.url, ErrorType.VALIDATION_ERROR, error_msg, attempt_number)
                return PriceCheckResult.error_result(
                    product.id, product.name, product.url, error_msg
                )
            
            # Validate price
            if not self._is_valid_price(product_info.price):
                error_msg = f"Invalid price value: {product_info.price}"
                self.logger.error(f"Invalid price for {product.url}: {error_msg}")
                self._record_error(product.id, product.url, ErrorType.VALIDATION_ERROR, error_msg, attempt_number)
                return PriceCheckResult.error_result(
                    product.id, product.name, product.url, error_msg
                )
            
            new_price = product_info.price
            old_price = product.current_price
            
            # Compare prices and detect drops
            price_dropped = new_price < old_price
            is_new_lowest = new_price < product.lowest_price
            
            # Update the product price
            update_success = self.product_service.update_product_price(
                product.id, new_price, 'automatic'
            )
            
            if not update_success:
                error_msg = "Failed to update product price in database"
                self.logger.error(f"Database update failed for product {product.id}")
                self._record_error(product.id, product.url, ErrorType.DATABASE_ERROR, error_msg, attempt_number)
                return PriceCheckResult.error_result(
                    product.id, product.name, product.url, error_msg
                )
            
            # Log the result
            if price_dropped:
                self.logger.info(f"Price drop detected for {product.name}: ${old_price:.2f} -> ${new_price:.2f}")
            elif is_new_lowest:
                self.logger.info(f"New lowest price for {product.name}: ${new_price:.2f}")
            else:
                self.logger.info(f"Price updated for {product.name}: ${old_price:.2f} -> ${new_price:.2f}")
            
            # Send email notification for any price change if email service is available
            notification_sent = False
            notification_error = None
            
            if self.email_service and (price_dropped or new_price != old_price):
                try:
                    # Get updated product data for notification
                    updated_product = self.product_service.get_product(product.id)
                    if updated_product:
                        notification_result = self.email_service.send_price_drop_notification(
                            updated_product, old_price, new_price, 'automatic'
                        )
                        notification_sent = notification_result.success
                        if not notification_result.success:
                            notification_error = notification_result.message
                            self.logger.warning(f"Failed to send notification for product {product.id}: {notification_result.message}")
                        else:
                            self.logger.info(f"Email notification sent for product {product.id}")
                    else:
                        notification_error = "Could not retrieve updated product data"
                        self.logger.warning(f"Could not retrieve updated product data for notification: {product.id}")
                except Exception as e:
                    notification_error = f"Notification error: {str(e)}"
                    self.logger.error(f"Error sending notification for product {product.id}: {str(e)}")
            
            return PriceCheckResult.success_result(
                product.id, product.name, product.url, old_price, new_price, 
                price_dropped, is_new_lowest, notification_sent, notification_error
            )
            
        except Exception as e:
            # This will be caught by the calling method
            raise
    
    def check_all_products(self, max_workers: Optional[int] = None) -> List[PriceCheckResult]:
        """
        Check prices for all active products.
        
        Args:
            max_workers: Maximum number of concurrent workers (defaults to max_concurrent_checks)
            
        Returns:
            List of PriceCheckResult for all products
        """
        if max_workers is None:
            max_workers = self.max_concurrent_checks
        
        # Get all active products
        products = self.product_service.get_products_for_monitoring()
        if not products:
            self.logger.info("No active products to monitor")
            return []
        
        self.logger.info(f"Starting price check for {len(products)} products")
        
        # Initialize statistics
        stats = MonitoringStats(
            total_products=len(products),
            successful_checks=0,
            failed_checks=0,
            price_drops_detected=0,
            new_lowest_prices=0,
            notifications_sent=0,
            notification_failures=0,
            start_time=datetime.now()
        )
        
        results = []
        
        # Use ThreadPoolExecutor for concurrent processing
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all tasks
            future_to_product = {
                executor.submit(self.check_product, product.id): product 
                for product in products
            }
            
            # Collect results as they complete
            for future in as_completed(future_to_product, timeout=self.check_timeout * len(products)):
                try:
                    result = future.result(timeout=self.check_timeout)
                    results.append(result)
                    
                    # Update statistics
                    if result.success:
                        stats.successful_checks += 1
                        if result.price_dropped:
                            stats.price_drops_detected += 1
                        if result.is_new_lowest:
                            stats.new_lowest_prices += 1
                        if result.notification_sent:
                            stats.notifications_sent += 1
                        if result.notification_error:
                            stats.notification_failures += 1
                    else:
                        stats.failed_checks += 1
                        
                except Exception as e:
                    product = future_to_product[future]
                    error_result = PriceCheckResult.error_result(
                        product.id, product.name, product.url, 
                        f"Task execution error: {str(e)}"
                    )
                    results.append(error_result)
                    stats.failed_checks += 1
        
        # Complete statistics
        stats.complete()
        self._last_run_stats = stats
        self._total_runs += 1
        self._total_price_drops += stats.price_drops_detected
        
        # Log summary
        self.logger.info(
            f"Price check completed: {stats.successful_checks}/{stats.total_products} successful, "
            f"{stats.price_drops_detected} price drops, {stats.new_lowest_prices} new lowest prices, "
            f"{stats.notifications_sent} notifications sent, {stats.notification_failures} notification failures, "
            f"duration: {stats.duration_seconds:.1f}s"
        )
        
        return results
    
    def schedule_daily_checks(self, check_time: str = "09:00") -> None:
        """
        Schedule daily price checks.
        
        Args:
            check_time: Time to run checks in HH:MM format (24-hour)
        """
        try:
            # Validate time format
            time.strptime(check_time, "%H:%M")
        except ValueError:
            raise ValueError(f"Invalid time format: {check_time}. Use HH:MM format.")
        
        # Clear existing schedule
        schedule.clear()
        
        # Schedule the daily check
        schedule.every().day.at(check_time).do(self._scheduled_check_wrapper)
        
        self.logger.info(f"Scheduled daily price checks at {check_time}")
    
    def start_scheduler(self, check_time: str = "09:00") -> None:
        """
        Start the scheduler in a background thread.
        
        Args:
            check_time: Time to run checks in HH:MM format (24-hour)
        """
        if self._scheduler_running:
            self.logger.warning("Scheduler is already running")
            return
        
        self.schedule_daily_checks(check_time)
        self._stop_scheduler.clear()
        self._scheduler_running = True
        
        # Start scheduler thread
        self._scheduler_thread = threading.Thread(target=self._run_scheduler, daemon=True)
        self._scheduler_thread.start()
        
        self.logger.info("Price monitoring scheduler started")
    
    def stop_scheduler(self) -> None:
        """Stop the scheduler."""
        if not self._scheduler_running:
            self.logger.warning("Scheduler is not running")
            return
        
        self._stop_scheduler.set()
        self._scheduler_running = False
        
        if self._scheduler_thread and self._scheduler_thread.is_alive():
            self._scheduler_thread.join(timeout=5)
        
        schedule.clear()
        self.logger.info("Price monitoring scheduler stopped")
    
    def _run_scheduler(self) -> None:
        """Run the scheduler loop."""
        while not self._stop_scheduler.is_set():
            try:
                schedule.run_pending()
                time.sleep(60)  # Check every minute
            except Exception as e:
                self.logger.error(f"Error in scheduler loop: {str(e)}")
                time.sleep(60)
    
    def _scheduled_check_wrapper(self) -> None:
        """Wrapper for scheduled checks with error handling."""
        try:
            self.logger.info("Starting scheduled price check")
            results = self.check_all_products()
            
            # Log results summary
            successful = sum(1 for r in results if r.success)
            price_drops = sum(1 for r in results if r.price_dropped)
            notifications_sent = sum(1 for r in results if r.notification_sent)
            
            self.logger.info(
                f"Scheduled check completed: {successful}/{len(results)} successful, "
                f"{price_drops} price drops detected, {notifications_sent} notifications sent"
            )
            
        except Exception as e:
            self.logger.error(f"Error in scheduled price check: {str(e)}")
    
    def get_monitoring_stats(self) -> Dict[str, Any]:
        """
        Get monitoring statistics.
        
        Returns:
            Dictionary with monitoring statistics
        """
        stats = {
            'total_runs': self._total_runs,
            'total_price_drops': self._total_price_drops,
            'scheduler_running': self._scheduler_running,
            'last_run': None
        }
        
        if self._last_run_stats:
            stats['last_run'] = {
                'timestamp': self._last_run_stats.start_time.isoformat(),
                'total_products': self._last_run_stats.total_products,
                'successful_checks': self._last_run_stats.successful_checks,
                'failed_checks': self._last_run_stats.failed_checks,
                'price_drops_detected': self._last_run_stats.price_drops_detected,
                'new_lowest_prices': self._last_run_stats.new_lowest_prices,
                'notifications_sent': self._last_run_stats.notifications_sent,
                'notification_failures': self._last_run_stats.notification_failures,
                'duration_seconds': self._last_run_stats.duration_seconds
            }
        
        return stats
    
    def get_next_scheduled_run(self) -> Optional[datetime]:
        """
        Get the next scheduled run time.
        
        Returns:
            Next scheduled run datetime or None if not scheduled
        """
        if not self._scheduler_running or not schedule.jobs:
            return None
        
        try:
            next_run = schedule.next_run()
            return next_run
        except Exception:
            return None
    
    def run_immediate_check(self, product_ids: Optional[List[int]] = None) -> List[PriceCheckResult]:
        """
        Run an immediate price check for specific products or all products.
        
        Args:
            product_ids: List of product IDs to check, or None for all products
            
        Returns:
            List of PriceCheckResult
        """
        if product_ids is None:
            return self.check_all_products()
        
        results = []
        for product_id in product_ids:
            result = self.check_product(product_id)
            results.append(result)
        
        return results
    
    def update_product_price_manually(self, product_id: int, new_price: float) -> PriceCheckResult:
        """
        Manually update a product's price and send notification if applicable.
        
        Args:
            product_id: Product ID
            new_price: New price value
            
        Returns:
            PriceCheckResult with the update outcome
        """
        try:
            # Get the product before update
            product = self.product_service.get_product(product_id)
            if not product:
                return PriceCheckResult.error_result(
                    product_id, "Unknown", "", f"Product with ID {product_id} not found"
                )
            
            if not product.is_active:
                return PriceCheckResult.error_result(
                    product_id, product.name, product.url, "Product is not active"
                )
            
            # Validate price
            if not self._is_valid_price(new_price):
                return PriceCheckResult.error_result(
                    product_id, product.name, product.url, f"Invalid price value: {new_price}"
                )
            
            old_price = product.current_price
            
            # Check if price actually changed
            if abs(new_price - old_price) < 0.01:  # Prices are essentially the same
                return PriceCheckResult.success_result(
                    product_id, product.name, product.url, old_price, new_price, 
                    False, False, False, "No price change detected"
                )
            
            # Update the product price
            update_success = self.product_service.update_product_price(
                product_id, new_price, 'manual'
            )
            
            if not update_success:
                return PriceCheckResult.error_result(
                    product_id, product.name, product.url, "Failed to update product price in database"
                )
            
            # Determine if this is a price drop and if it's a new lowest
            price_dropped = new_price < old_price
            is_new_lowest = new_price < product.lowest_price
            
            # Log the manual update
            if price_dropped:
                self.logger.info(f"Manual price drop for {product.name}: ${old_price:.2f} -> ${new_price:.2f}")
            else:
                self.logger.info(f"Manual price update for {product.name}: ${old_price:.2f} -> ${new_price:.2f}")
            
            # Send email notification for any price change if email service is available
            notification_sent = False
            notification_error = None
            
            if self.email_service:
                try:
                    # Get updated product data for notification
                    updated_product = self.product_service.get_product(product_id)
                    if updated_product:
                        notification_result = self.email_service.send_price_drop_notification(
                            updated_product, old_price, new_price, 'manual'
                        )
                        notification_sent = notification_result.success
                        if not notification_result.success:
                            notification_error = notification_result.message
                            self.logger.warning(f"Failed to send manual update notification for product {product_id}: {notification_result.message}")
                        else:
                            self.logger.info(f"Manual update email notification sent for product {product_id}")
                    else:
                        notification_error = "Could not retrieve updated product data"
                        self.logger.warning(f"Could not retrieve updated product data for manual update notification: {product_id}")
                except Exception as e:
                    notification_error = f"Notification error: {str(e)}"
                    self.logger.error(f"Error sending manual update notification for product {product_id}: {str(e)}")
            
            return PriceCheckResult.success_result(
                product_id, product.name, product.url, old_price, new_price, 
                price_dropped, is_new_lowest, notification_sent, notification_error
            )
            
        except Exception as e:
            self.logger.error(f"Error in manual price update for product {product_id}: {str(e)}")
            return PriceCheckResult.error_result(
                product_id, "Unknown", "", f"Manual update error: {str(e)}"
            )
    
    def is_scheduler_running(self) -> bool:
        """Check if the scheduler is currently running."""
        return self._scheduler_running
    
    def get_price_comparison_summary(self, product_id: int, days: int = 30) -> Dict[str, Any]:
        """
        Get a price comparison summary for a product over the specified period.
        
        Args:
            product_id: Product ID
            days: Number of days to look back
            
        Returns:
            Dictionary with price comparison data
        """
        try:
            product = self.product_service.get_product(product_id)
            if not product:
                return {'error': 'Product not found'}
            
            # Get price history for the period
            price_history = self.product_service.get_price_history(product_id)
            
            # Filter by date range
            cutoff_date = datetime.now() - timedelta(days=days)
            recent_history = [
                entry for entry in price_history 
                if entry.recorded_at >= cutoff_date
            ]
            
            if not recent_history:
                return {
                    'product_name': product.name,
                    'current_price': product.current_price,
                    'lowest_price': product.lowest_price,
                    'price_changes': 0,
                    'average_price': product.current_price,
                    'price_trend': 'stable'
                }
            
            prices = [entry.price for entry in recent_history]
            price_changes = len(recent_history) - 1
            average_price = sum(prices) / len(prices)
            
            # Determine trend (prices[0] is most recent, prices[-1] is oldest)
            if len(prices) >= 2:
                if prices[0] > prices[-1]:  # Most recent > oldest = increasing
                    trend = 'increasing'
                elif prices[0] < prices[-1]:  # Most recent < oldest = decreasing
                    trend = 'decreasing'
                else:
                    trend = 'stable'
            else:
                trend = 'stable'
            
            return {
                'product_name': product.name,
                'current_price': product.current_price,
                'lowest_price': product.lowest_price,
                'highest_price_in_period': max(prices),
                'lowest_price_in_period': min(prices),
                'price_changes': price_changes,
                'average_price': round(average_price, 2),
                'price_trend': trend,
                'days_analyzed': days
            }
            
        except Exception as e:
            self.logger.error(f"Error getting price comparison for product {product_id}: {str(e)}")
            return {'error': str(e)}
    
    def _should_skip_url(self, url: str) -> bool:
        """
        Check if a URL should be skipped due to recent failures.
        
        Args:
            url: URL to check
            
        Returns:
            True if URL should be skipped, False otherwise
        """
        if url not in self._failed_urls:
            return False
        
        last_failure = self._failed_urls[url]
        # Skip URLs that failed in the last hour
        return datetime.now() - last_failure < timedelta(hours=1)
    
    def _calculate_retry_delay(self, attempt_number: int) -> float:
        """
        Calculate delay before retry using exponential backoff.
        
        Args:
            attempt_number: Current attempt number (0-based)
            
        Returns:
            Delay in seconds
        """
        return self.retry_delay * (self.backoff_factor ** attempt_number)
    
    def _record_failure(self, product_id: int, url: str, error_message: str, attempt_number: int):
        """
        Record a failure for tracking purposes.
        
        Args:
            product_id: Product ID
            url: Product URL
            error_message: Error message
            attempt_number: Attempt number
        """
        self._consecutive_failures[product_id] = self._consecutive_failures.get(product_id, 0) + 1
        self._failed_urls[url] = datetime.now()
        
        self.logger.warning(
            f"Price check failed for product {product_id} (attempt {attempt_number + 1}): {error_message}"
        )
    
    def _record_error(self, product_id: int, url: str, error_type: ErrorType, 
                     error_message: str, retry_count: int):
        """
        Record an error in the error history.
        
        Args:
            product_id: Product ID
            url: Product URL
            error_type: Type of error
            error_message: Error message
            retry_count: Number of retries attempted
        """
        error_record = ErrorRecord(
            product_id=product_id,
            product_url=url,
            error_type=error_type,
            error_message=error_message,
            timestamp=datetime.now(),
            retry_count=retry_count
        )
        
        self._error_history.append(error_record)
        
        # Keep only the last 1000 error records to prevent memory issues
        if len(self._error_history) > 1000:
            self._error_history = self._error_history[-1000:]
    
    def _reset_failure_tracking(self, product_id: int, url: str):
        """
        Reset failure tracking for a product after successful check.
        
        Args:
            product_id: Product ID
            url: Product URL
        """
        if product_id in self._consecutive_failures:
            del self._consecutive_failures[product_id]
        
        if url in self._failed_urls:
            del self._failed_urls[url]
    
    def _handle_persistent_failure(self, product_id: int, url: str):
        """
        Handle a product that has failed all retry attempts.
        
        Args:
            product_id: Product ID
            url: Product URL
        """
        failure_count = self._consecutive_failures.get(product_id, 0)
        
        self.logger.error(
            f"Product {product_id} ({url}) failed all {self.max_retries + 1} attempts. "
            f"Total consecutive failures: {failure_count}"
        )
        
        # If a product fails too many times, consider deactivating it
        if failure_count >= 10:  # Configurable threshold
            self.logger.warning(
                f"Product {product_id} has failed {failure_count} consecutive times. "
                "Consider deactivating or checking the URL manually."
            )
    
    def _is_valid_price(self, price: float) -> bool:
        """
        Validate that a price value is reasonable.
        
        Args:
            price: Price to validate
            
        Returns:
            True if price is valid, False otherwise
        """
        if price is None:
            return False
        
        # Price should be positive
        if price <= 0:
            return False
        
        # Price should be reasonable (not too high)
        if price > 1000000:  # $1M seems like a reasonable upper limit
            return False
        
        # Price should not be too small (likely parsing error)
        if price < 0.01:
            return False
        
        return True
    
    def get_error_summary(self, hours: int = 24) -> Dict[str, Any]:
        """
        Get a summary of errors that occurred in the specified time period.
        
        Args:
            hours: Number of hours to look back
            
        Returns:
            Dictionary with error summary
        """
        cutoff_time = datetime.now() - timedelta(hours=hours)
        recent_errors = [
            error for error in self._error_history 
            if error.timestamp >= cutoff_time
        ]
        
        if not recent_errors:
            return {
                'total_errors': 0,
                'error_types': {},
                'most_common_errors': [],
                'affected_products': 0,
                'time_period_hours': hours
            }
        
        # Count errors by type
        error_type_counts = {}
        for error in recent_errors:
            error_type = error.error_type.value
            error_type_counts[error_type] = error_type_counts.get(error_type, 0) + 1
        
        # Find most common error messages
        error_message_counts = {}
        for error in recent_errors:
            msg = error.error_message[:100]  # Truncate long messages
            error_message_counts[msg] = error_message_counts.get(msg, 0) + 1
        
        most_common_errors = sorted(
            error_message_counts.items(), 
            key=lambda x: x[1], 
            reverse=True
        )[:5]
        
        # Count affected products
        affected_products = len(set(error.product_id for error in recent_errors))
        
        return {
            'total_errors': len(recent_errors),
            'error_types': error_type_counts,
            'most_common_errors': most_common_errors,
            'affected_products': affected_products,
            'time_period_hours': hours
        }
    
    def get_failing_products(self) -> List[Dict[str, Any]]:
        """
        Get a list of products that are currently failing.
        
        Returns:
            List of dictionaries with failing product information
        """
        failing_products = []
        
        for product_id, failure_count in self._consecutive_failures.items():
            if failure_count > 0:
                product = self.product_service.get_product(product_id)
                if product:
                    failing_products.append({
                        'product_id': product_id,
                        'product_name': product.name,
                        'product_url': product.url,
                        'consecutive_failures': failure_count,
                        'last_failure_time': self._failed_urls.get(product.url)
                    })
        
        # Sort by failure count (highest first)
        failing_products.sort(key=lambda x: x['consecutive_failures'], reverse=True)
        
        return failing_products
    
    def clear_error_history(self):
        """Clear the error history and failure tracking."""
        self._error_history.clear()
        self._failed_urls.clear()
        self._consecutive_failures.clear()
        self.logger.info("Error history and failure tracking cleared")
    
    def retry_failed_products(self) -> List[PriceCheckResult]:
        """
        Retry price checks for products that are currently marked as failing.
        
        Returns:
            List of PriceCheckResult for retried products
        """
        failing_product_ids = list(self._consecutive_failures.keys())
        
        if not failing_product_ids:
            self.logger.info("No failing products to retry")
            return []
        
        self.logger.info(f"Retrying {len(failing_product_ids)} failing products")
        
        # Clear failure tracking before retry
        self.clear_error_history()
        
        # Retry the products
        results = []
        for product_id in failing_product_ids:
            result = self.check_product(product_id)
            results.append(result)
        
        return results