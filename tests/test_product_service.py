"""
Unit tests for the ProductService class.
"""

import unittest
import tempfile
import os
from datetime import datetime, timedelta

from src.models.database import get_database_manager, Product, PriceHistory
from src.services.product_service import ProductService


class TestProductService(unittest.TestCase):
    """Test cases for ProductService."""
    
    def setUp(self):
        """Set up test database and service."""
        # Create temporary database for testing
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()
        
        # Create database manager with test database
        self.db_manager = get_database_manager(f"sqlite:///{self.temp_db.name}")
        self.db_manager.create_tables()
        
        # Create product service
        self.product_service = ProductService(self.db_manager)
    
    def tearDown(self):
        """Clean up test database."""
        os.unlink(self.temp_db.name)
    
    def test_add_product_success(self):
        """Test successfully adding a new product."""
        product = self.product_service.add_product(
            url="https://example.com/product1",
            name="Test Product",
            price=99.99,
            image_url="https://example.com/image.jpg"
        )
        
        self.assertIsNotNone(product)
        self.assertEqual(product.url, "https://example.com/product1")
        self.assertEqual(product.name, "Test Product")
        self.assertEqual(product.current_price, 99.99)
        self.assertEqual(product.lowest_price, 99.99)
        self.assertIsNone(product.previous_price)
        self.assertTrue(product.is_active)
    
    def test_add_duplicate_product_fails(self):
        """Test that adding a duplicate product fails."""
        # Add first product
        product1 = self.product_service.add_product(
            url="https://example.com/product1",
            name="Test Product",
            price=99.99
        )
        self.assertIsNotNone(product1)
        
        # Try to add duplicate
        product2 = self.product_service.add_product(
            url="https://example.com/product1",
            name="Duplicate Product",
            price=89.99
        )
        self.assertIsNone(product2)
    
    def test_get_product_by_id(self):
        """Test getting a product by ID."""
        # Add product
        product = self.product_service.add_product(
            url="https://example.com/product1",
            name="Test Product",
            price=99.99
        )
        
        # Get product by ID
        retrieved_product = self.product_service.get_product(product.id)
        self.assertIsNotNone(retrieved_product)
        self.assertEqual(retrieved_product.id, product.id)
        self.assertEqual(retrieved_product.name, "Test Product")
    
    def test_get_product_by_url(self):
        """Test getting a product by URL."""
        # Add product
        product = self.product_service.add_product(
            url="https://example.com/product1",
            name="Test Product",
            price=99.99
        )
        
        # Get product by URL
        retrieved_product = self.product_service.get_product_by_url("https://example.com/product1")
        self.assertIsNotNone(retrieved_product)
        self.assertEqual(retrieved_product.id, product.id)
        self.assertEqual(retrieved_product.url, "https://example.com/product1")
    
    def test_get_all_products(self):
        """Test getting all products."""
        # Add multiple products
        product1 = self.product_service.add_product(
            url="https://example.com/product1",
            name="Product 1",
            price=99.99
        )
        product2 = self.product_service.add_product(
            url="https://example.com/product2",
            name="Product 2",
            price=149.99
        )
        
        # Get all products
        products = self.product_service.get_all_products()
        self.assertEqual(len(products), 2)
        
        # Check products are ordered by creation date (newest first)
        self.assertEqual(products[0].id, product2.id)
        self.assertEqual(products[1].id, product1.id)
    
    def test_get_all_products_active_only(self):
        """Test getting only active products."""
        # Add products
        product1 = self.product_service.add_product(
            url="https://example.com/product1",
            name="Product 1",
            price=99.99
        )
        product2 = self.product_service.add_product(
            url="https://example.com/product2",
            name="Product 2",
            price=149.99
        )
        
        # Deactivate one product
        self.product_service.deactivate_product(product1.id)
        
        # Get active products only
        active_products = self.product_service.get_all_products(active_only=True)
        self.assertEqual(len(active_products), 1)
        self.assertEqual(active_products[0].id, product2.id)
        
        # Get all products including inactive
        all_products = self.product_service.get_all_products(active_only=False)
        self.assertEqual(len(all_products), 2)
    
    def test_update_product_price(self):
        """Test updating a product's price."""
        # Add product
        product = self.product_service.add_product(
            url="https://example.com/product1",
            name="Test Product",
            price=99.99
        )
        
        # Update price
        success = self.product_service.update_product_price(product.id, 89.99, 'automatic')
        self.assertTrue(success)
        
        # Verify price update
        updated_product = self.product_service.get_product(product.id)
        self.assertEqual(updated_product.current_price, 89.99)
        self.assertEqual(updated_product.previous_price, 99.99)
        self.assertEqual(updated_product.lowest_price, 89.99)  # Should be updated to new lower price
    
    def test_update_product_price_higher(self):
        """Test updating a product's price to a higher value."""
        # Add product
        product = self.product_service.add_product(
            url="https://example.com/product1",
            name="Test Product",
            price=99.99
        )
        
        # Update to higher price
        success = self.product_service.update_product_price(product.id, 109.99, 'manual')
        self.assertTrue(success)
        
        # Verify price update
        updated_product = self.product_service.get_product(product.id)
        self.assertEqual(updated_product.current_price, 109.99)
        self.assertEqual(updated_product.previous_price, 99.99)
        self.assertEqual(updated_product.lowest_price, 99.99)  # Should remain the same
    
    def test_delete_product(self):
        """Test deleting a product."""
        # Add product
        product = self.product_service.add_product(
            url="https://example.com/product1",
            name="Test Product",
            price=99.99
        )
        
        # Delete product
        success = self.product_service.delete_product(product.id)
        self.assertTrue(success)
        
        # Verify product is deleted
        deleted_product = self.product_service.get_product(product.id)
        self.assertIsNone(deleted_product)
    
    def test_deactivate_product(self):
        """Test deactivating a product."""
        # Add product
        product = self.product_service.add_product(
            url="https://example.com/product1",
            name="Test Product",
            price=99.99
        )
        
        # Deactivate product
        success = self.product_service.deactivate_product(product.id)
        self.assertTrue(success)
        
        # Verify product is deactivated
        deactivated_product = self.product_service.get_product(product.id)
        self.assertIsNotNone(deactivated_product)
        self.assertFalse(deactivated_product.is_active)
    
    def test_get_price_history(self):
        """Test getting price history for a product."""
        # Add product
        product = self.product_service.add_product(
            url="https://example.com/product1",
            name="Test Product",
            price=99.99
        )
        
        # Update price multiple times
        self.product_service.update_product_price(product.id, 89.99, 'automatic')
        self.product_service.update_product_price(product.id, 79.99, 'manual')
        
        # Get price history
        history = self.product_service.get_price_history(product.id)
        
        # Should have 3 entries (initial + 2 updates)
        self.assertEqual(len(history), 3)
        
        # Check order (newest first)
        self.assertEqual(history[0].price, 79.99)
        self.assertEqual(history[0].source, 'manual')
        self.assertEqual(history[1].price, 89.99)
        self.assertEqual(history[1].source, 'automatic')
        self.assertEqual(history[2].price, 99.99)
        self.assertEqual(history[2].source, 'manual')  # Initial price is marked as manual
    
    def test_get_price_history_with_limit(self):
        """Test getting price history with a limit."""
        # Add product
        product = self.product_service.add_product(
            url="https://example.com/product1",
            name="Test Product",
            price=99.99
        )
        
        # Update price multiple times
        self.product_service.update_product_price(product.id, 89.99, 'automatic')
        self.product_service.update_product_price(product.id, 79.99, 'manual')
        
        # Get limited price history
        history = self.product_service.get_price_history(product.id, limit=2)
        
        # Should have only 2 entries (most recent)
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0].price, 79.99)
        self.assertEqual(history[1].price, 89.99)
    
    def test_get_lowest_price(self):
        """Test getting the lowest price for a product."""
        # Add product
        product = self.product_service.add_product(
            url="https://example.com/product1",
            name="Test Product",
            price=99.99
        )
        
        # Update prices
        self.product_service.update_product_price(product.id, 109.99, 'automatic')  # Higher
        self.product_service.update_product_price(product.id, 79.99, 'manual')     # Lower
        self.product_service.update_product_price(product.id, 89.99, 'automatic')  # Higher again
        
        # Get lowest price
        lowest_price = self.product_service.get_lowest_price(product.id)
        self.assertEqual(lowest_price, 79.99)
    
    def test_has_price_dropped(self):
        """Test checking if price has dropped."""
        # Add product
        product = self.product_service.add_product(
            url="https://example.com/product1",
            name="Test Product",
            price=99.99
        )
        
        # Initially no previous price, so no drop
        has_dropped, prev_price, curr_price = self.product_service.has_price_dropped(product.id)
        self.assertFalse(has_dropped)
        
        # Update to lower price
        self.product_service.update_product_price(product.id, 89.99, 'automatic')
        has_dropped, prev_price, curr_price = self.product_service.has_price_dropped(product.id)
        self.assertTrue(has_dropped)
        self.assertEqual(prev_price, 99.99)
        self.assertEqual(curr_price, 89.99)
        
        # Update to higher price
        self.product_service.update_product_price(product.id, 109.99, 'automatic')
        has_dropped, prev_price, curr_price = self.product_service.has_price_dropped(product.id)
        self.assertFalse(has_dropped)
        self.assertEqual(prev_price, 89.99)
        self.assertEqual(curr_price, 109.99)
    
    def test_get_products_for_monitoring(self):
        """Test getting products for monitoring."""
        # Add products
        product1 = self.product_service.add_product(
            url="https://example.com/product1",
            name="Product 1",
            price=99.99
        )
        product2 = self.product_service.add_product(
            url="https://example.com/product2",
            name="Product 2",
            price=149.99
        )
        
        # Deactivate one product
        self.product_service.deactivate_product(product1.id)
        
        # Get products for monitoring (should only return active ones)
        monitoring_products = self.product_service.get_products_for_monitoring()
        self.assertEqual(len(monitoring_products), 1)
        self.assertEqual(monitoring_products[0].id, product2.id)
    
    def test_get_product_statistics(self):
        """Test getting product statistics."""
        # Add products
        product1 = self.product_service.add_product(
            url="https://example.com/product1",
            name="Product 1",
            price=99.99
        )
        product2 = self.product_service.add_product(
            url="https://example.com/product2",
            name="Product 2",
            price=149.99
        )
        product3 = self.product_service.add_product(
            url="https://example.com/product3",
            name="Product 3",
            price=199.99
        )
        
        # Deactivate one product
        self.product_service.deactivate_product(product3.id)
        
        # Create price drops
        self.product_service.update_product_price(product1.id, 89.99, 'automatic')  # Price drop
        self.product_service.update_product_price(product2.id, 159.99, 'automatic')  # Price increase
        
        # Get statistics
        stats = self.product_service.get_product_statistics()
        
        self.assertEqual(stats['total_products'], 3)
        self.assertEqual(stats['active_products'], 2)
        self.assertEqual(stats['inactive_products'], 1)
        self.assertEqual(stats['recent_price_drops'], 1)


if __name__ == '__main__':
    unittest.main()