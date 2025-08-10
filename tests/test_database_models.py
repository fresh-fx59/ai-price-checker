"""
Unit tests for database models and database manager.
"""

import unittest
import tempfile
import os
from datetime import datetime

from src.models.database import get_database_manager, Product, PriceHistory, DatabaseManager
from src.models.migrations import run_migrations


class TestDatabaseModels(unittest.TestCase):
    """Test cases for database models."""
    
    def setUp(self):
        """Set up test database."""
        # Create temporary database for testing
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()
        
        # Create database manager with test database
        self.db_manager = get_database_manager(f"sqlite:///{self.temp_db.name}")
        self.db_manager.create_tables()
    
    def tearDown(self):
        """Clean up test database."""
        os.unlink(self.temp_db.name)
    
    def test_database_manager_creation(self):
        """Test database manager creation."""
        self.assertIsInstance(self.db_manager, DatabaseManager)
        self.assertIsNotNone(self.db_manager.engine)
        self.assertIsNotNone(self.db_manager.SessionLocal)
    
    def test_database_manager_default_path(self):
        """Test database manager with default path."""
        # Create manager without specifying path
        default_manager = get_database_manager()
        self.assertIsInstance(default_manager, DatabaseManager)
        self.assertTrue(default_manager.database_url.startswith('sqlite:///'))
    
    def test_product_model_creation(self):
        """Test creating a Product model instance."""
        with self.db_manager.get_session() as session:
            product = Product(
                url="https://example.com/product1",
                name="Test Product",
                current_price=99.99,
                lowest_price=99.99,
                created_at=datetime.now(),
                is_active=True
            )
            
            session.add(product)
            session.commit()
            session.refresh(product)
            
            # Verify product was created
            self.assertIsNotNone(product.id)
            self.assertEqual(product.url, "https://example.com/product1")
            self.assertEqual(product.name, "Test Product")
            self.assertEqual(product.current_price, 99.99)
            self.assertEqual(product.lowest_price, 99.99)
            self.assertTrue(product.is_active)
    
    def test_product_model_unique_url_constraint(self):
        """Test that product URLs must be unique."""
        with self.db_manager.get_session() as session:
            # Create first product
            product1 = Product(
                url="https://example.com/product1",
                name="Test Product 1",
                current_price=99.99,
                lowest_price=99.99,
                created_at=datetime.now(),
                is_active=True
            )
            session.add(product1)
            session.commit()
            
            # Try to create second product with same URL
            product2 = Product(
                url="https://example.com/product1",  # Same URL
                name="Test Product 2",
                current_price=149.99,
                lowest_price=149.99,
                created_at=datetime.now(),
                is_active=True
            )
            session.add(product2)
            
            # This should raise an integrity error
            with self.assertRaises(Exception):
                session.commit()
    
    def test_price_history_model_creation(self):
        """Test creating a PriceHistory model instance."""
        with self.db_manager.get_session() as session:
            # First create a product
            product = Product(
                url="https://example.com/product1",
                name="Test Product",
                current_price=99.99,
                lowest_price=99.99,
                created_at=datetime.now(),
                is_active=True
            )
            session.add(product)
            session.commit()
            session.refresh(product)
            
            # Create price history entry
            price_history = PriceHistory(
                product_id=product.id,
                price=99.99,
                recorded_at=datetime.now(),
                source='manual'
            )
            session.add(price_history)
            session.commit()
            session.refresh(price_history)
            
            # Verify price history was created
            self.assertIsNotNone(price_history.id)
            self.assertEqual(price_history.product_id, product.id)
            self.assertEqual(price_history.price, 99.99)
            self.assertEqual(price_history.source, 'manual')
    
    def test_product_price_history_relationship(self):
        """Test the relationship between Product and PriceHistory."""
        with self.db_manager.get_session() as session:
            # Create product
            product = Product(
                url="https://example.com/product1",
                name="Test Product",
                current_price=99.99,
                lowest_price=99.99,
                created_at=datetime.now(),
                is_active=True
            )
            session.add(product)
            session.commit()
            session.refresh(product)
            
            # Create multiple price history entries
            for i, price in enumerate([99.99, 89.99, 79.99]):
                price_history = PriceHistory(
                    product_id=product.id,
                    price=price,
                    recorded_at=datetime.now(),
                    source='automatic' if i > 0 else 'manual'
                )
                session.add(price_history)
            
            session.commit()
            
            # Test relationship from product to price history
            product_with_history = session.query(Product).filter(Product.id == product.id).first()
            self.assertEqual(len(product_with_history.price_history), 3)
            
            # Test relationship from price history to product
            price_history_entry = session.query(PriceHistory).filter(
                PriceHistory.product_id == product.id
            ).first()
            self.assertEqual(price_history_entry.product.id, product.id)
            self.assertEqual(price_history_entry.product.name, "Test Product")
    
    def test_product_cascade_delete(self):
        """Test that deleting a product cascades to price history."""
        with self.db_manager.get_session() as session:
            # Create product with price history
            product = Product(
                url="https://example.com/product1",
                name="Test Product",
                current_price=99.99,
                lowest_price=99.99,
                created_at=datetime.now(),
                is_active=True
            )
            session.add(product)
            session.commit()
            session.refresh(product)
            
            # Add price history
            price_history = PriceHistory(
                product_id=product.id,
                price=99.99,
                recorded_at=datetime.now(),
                source='manual'
            )
            session.add(price_history)
            session.commit()
            
            # Verify both exist
            self.assertIsNotNone(session.query(Product).filter(Product.id == product.id).first())
            self.assertIsNotNone(session.query(PriceHistory).filter(PriceHistory.product_id == product.id).first())
            
            # Delete product
            session.delete(product)
            session.commit()
            
            # Verify product and price history are both deleted
            self.assertIsNone(session.query(Product).filter(Product.id == product.id).first())
            self.assertIsNone(session.query(PriceHistory).filter(PriceHistory.product_id == product.id).first())
    
    def test_database_session_management(self):
        """Test database session management."""
        # Test that sessions are properly created and closed
        session1 = self.db_manager.get_session()
        session2 = self.db_manager.get_session()
        
        # Should be different session instances
        self.assertIsNot(session1, session2)
        
        # Close sessions
        session1.close()
        session2.close()
    
    def test_migrations_integration(self):
        """Test that migrations work with the database."""
        # Create a fresh database manager
        temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        temp_db.close()
        
        try:
            db_manager = get_database_manager(f"sqlite:///{temp_db.name}")
            
            # Run migrations
            run_migrations(db_manager)
            
            # Verify tables exist by creating a product
            with db_manager.get_session() as session:
                product = Product(
                    url="https://example.com/test",
                    name="Migration Test",
                    current_price=50.0,
                    lowest_price=50.0,
                    created_at=datetime.now(),
                    is_active=True
                )
                session.add(product)
                session.commit()
                
                # Verify product was created successfully
                retrieved_product = session.query(Product).filter(Product.url == "https://example.com/test").first()
                self.assertIsNotNone(retrieved_product)
                self.assertEqual(retrieved_product.name, "Migration Test")
        
        finally:
            os.unlink(temp_db.name)


if __name__ == '__main__':
    unittest.main()