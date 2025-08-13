"""
Product service for managing products and price history in the Price Monitor application.
"""

from datetime import datetime
from typing import List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import desc, func

from ..models.database import Product, PriceHistory, DatabaseManager


class ProductService:
    """Service class for managing products and their price history."""
    
    def __init__(self, db_manager: DatabaseManager):
        """
        Initialize the product service.
        
        Args:
            db_manager: Database manager instance
        """
        self.db_manager = db_manager
    
    def add_product(self, url: str, name: str, price: float, image_url: Optional[str] = None) -> Optional[Product]:
        """
        Add a new product to monitor.
        
        Args:
            url: Product URL
            name: Product name
            price: Initial price
            image_url: Optional product image URL
            
        Returns:
            Product instance if successful, None if failed
        """
        try:
            session = self.db_manager.get_session()
            try:
                # Check if product with this URL already exists
                existing_product = session.query(Product).filter(Product.url == url).first()
                if existing_product:
                    raise ValueError(f"Product with URL {url} already exists")
                
                # Create new product
                product = Product(
                    url=url,
                    name=name,
                    current_price=price,
                    previous_price=None,
                    lowest_price=price,
                    image_url=image_url,
                    created_at=datetime.now(),
                    last_checked=datetime.now(),
                    is_active=True
                )
                
                session.add(product)
                session.commit()
                session.refresh(product)
                
                # Add initial price history entry
                self._add_price_history(session, product.id, price, 'manual')
                session.commit()
                
                # Create a new instance with the data to avoid session issues
                product_data = {
                    'id': product.id,
                    'url': product.url,
                    'name': product.name,
                    'current_price': product.current_price,
                    'previous_price': product.previous_price,
                    'lowest_price': product.lowest_price,
                    'image_url': product.image_url,
                    'created_at': product.created_at,
                    'last_checked': product.last_checked,
                    'is_active': product.is_active
                }
                
                # Create a detached product instance
                detached_product = Product(**product_data)
                return detached_product
                
            finally:
                session.close()
                
        except SQLAlchemyError as e:
            print(f"Database error adding product: {e}")
            return None
        except Exception as e:
            print(f"Error adding product: {e}")
            return None
    
    def get_product(self, product_id: int) -> Optional[Product]:
        """
        Get a product by ID.
        
        Args:
            product_id: Product ID
            
        Returns:
            Product instance if found, None otherwise
        """
        try:
            session = self.db_manager.get_session()
            try:
                product = session.query(Product).filter(Product.id == product_id).first()
                if product:
                    # Create a detached instance
                    product_data = {
                        'id': product.id,
                        'url': product.url,
                        'name': product.name,
                        'current_price': product.current_price,
                        'previous_price': product.previous_price,
                        'lowest_price': product.lowest_price,
                        'image_url': product.image_url,
                        'created_at': product.created_at,
                        'last_checked': product.last_checked,
                        'is_active': product.is_active
                    }
                    return Product(**product_data)
                return None
            finally:
                session.close()
        except SQLAlchemyError as e:
            print(f"Database error getting product: {e}")
            return None
    
    def get_product_by_url(self, url: str) -> Optional[Product]:
        """
        Get a product by URL.
        
        Args:
            url: Product URL
            
        Returns:
            Product instance if found, None otherwise
        """
        try:
            session = self.db_manager.get_session()
            try:
                product = session.query(Product).filter(Product.url == url).first()
                if product:
                    # Create a detached instance
                    product_data = {
                        'id': product.id,
                        'url': product.url,
                        'name': product.name,
                        'current_price': product.current_price,
                        'previous_price': product.previous_price,
                        'lowest_price': product.lowest_price,
                        'image_url': product.image_url,
                        'created_at': product.created_at,
                        'last_checked': product.last_checked,
                        'is_active': product.is_active
                    }
                    return Product(**product_data)
                return None
            finally:
                session.close()
        except SQLAlchemyError as e:
            print(f"Database error getting product by URL: {e}")
            return None
    
    def get_all_products(self, active_only: bool = True) -> List[Product]:
        """
        Get all products.
        
        Args:
            active_only: If True, only return active products
            
        Returns:
            List of Product instances
        """
        try:
            session = self.db_manager.get_session()
            try:
                query = session.query(Product)
                if active_only:
                    query = query.filter(Product.is_active == True)
                products = query.order_by(Product.created_at.desc()).all()
                
                # Create detached instances
                detached_products = []
                for product in products:
                    product_data = {
                        'id': product.id,
                        'url': product.url,
                        'name': product.name,
                        'current_price': product.current_price,
                        'previous_price': product.previous_price,
                        'lowest_price': product.lowest_price,
                        'image_url': product.image_url,
                        'created_at': product.created_at,
                        'last_checked': product.last_checked,
                        'is_active': product.is_active
                    }
                    detached_products.append(Product(**product_data))
                
                return detached_products
            finally:
                session.close()
        except SQLAlchemyError as e:
            print(f"Database error getting all products: {e}")
            return []
    
    def update_product_price(self, product_id: int, new_price: float, source: str = 'automatic') -> bool:
        """
        Update a product's price and track the change.
        
        Args:
            product_id: Product ID
            new_price: New price value
            source: Source of the price update ('automatic' or 'manual')
            
        Returns:
            True if successful, False otherwise
        """
        try:
            with self.db_manager.get_session() as session:
                product = session.query(Product).filter(Product.id == product_id).first()
                if not product:
                    print(f"Product with ID {product_id} not found")
                    return False
                
                # Update previous price and current price
                product.previous_price = product.current_price
                product.current_price = new_price
                product.last_checked = datetime.now()
                
                # Update lowest price if this is lower
                if new_price < product.lowest_price:
                    product.lowest_price = new_price
                
                # Add price history entry
                self._add_price_history(session, product_id, new_price, source)
                
                session.commit()
                return True
                
        except SQLAlchemyError as e:
            print(f"Database error updating product price: {e}")
            return False
        except Exception as e:
            print(f"Error updating product price: {e}")
            return False
    
    def delete_product(self, product_id: int) -> bool:
        """
        Delete a product and its price history.
        
        Args:
            product_id: Product ID
            
        Returns:
            True if successful, False otherwise
        """
        try:
            with self.db_manager.get_session() as session:
                product = session.query(Product).filter(Product.id == product_id).first()
                if not product:
                    print(f"Product with ID {product_id} not found in database")
                    return False
                
                print(f"Deleting product: {product.name} (ID: {product_id})")
                
                # Delete product (price history will be deleted due to cascade)
                session.delete(product)
                session.commit()
                
                print(f"Successfully deleted product {product_id} from database")
                return True
                
        except SQLAlchemyError as e:
            print(f"Database error deleting product {product_id}: {e}")
            import traceback
            traceback.print_exc()
            return False
        except Exception as e:
            print(f"Unexpected error deleting product {product_id}: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def deactivate_product(self, product_id: int) -> bool:
        """
        Deactivate a product (soft delete).
        
        Args:
            product_id: Product ID
            
        Returns:
            True if successful, False otherwise
        """
        try:
            with self.db_manager.get_session() as session:
                product = session.query(Product).filter(Product.id == product_id).first()
                if not product:
                    print(f"Product with ID {product_id} not found")
                    return False
                
                product.is_active = False
                session.commit()
                return True
                
        except SQLAlchemyError as e:
            print(f"Database error deactivating product: {e}")
            return False
    
    def get_price_history(self, product_id: int, limit: Optional[int] = None) -> List[PriceHistory]:
        """
        Get price history for a product.
        
        Args:
            product_id: Product ID
            limit: Optional limit on number of records to return
            
        Returns:
            List of PriceHistory instances
        """
        try:
            session = self.db_manager.get_session()
            try:
                query = session.query(PriceHistory).filter(
                    PriceHistory.product_id == product_id
                ).order_by(desc(PriceHistory.recorded_at))
                
                if limit:
                    query = query.limit(limit)
                
                history = query.all()
                
                # Create detached instances
                detached_history = []
                for entry in history:
                    history_data = {
                        'id': entry.id,
                        'product_id': entry.product_id,
                        'price': entry.price,
                        'recorded_at': entry.recorded_at,
                        'source': entry.source
                    }
                    detached_history.append(PriceHistory(**history_data))
                
                return detached_history
            finally:
                session.close()
                
        except SQLAlchemyError as e:
            print(f"Database error getting price history: {e}")
            return []
    
    def get_lowest_price(self, product_id: int) -> Optional[float]:
        """
        Get the lowest price ever recorded for a product.
        
        Args:
            product_id: Product ID
            
        Returns:
            Lowest price if found, None otherwise
        """
        try:
            with self.db_manager.get_session() as session:
                product = session.query(Product).filter(Product.id == product_id).first()
                return product.lowest_price if product else None
        except SQLAlchemyError as e:
            print(f"Database error getting lowest price: {e}")
            return None
    
    def has_price_dropped(self, product_id: int) -> Tuple[bool, Optional[float], Optional[float]]:
        """
        Check if the price has dropped for a product.
        
        Args:
            product_id: Product ID
            
        Returns:
            Tuple of (has_dropped, previous_price, current_price)
        """
        try:
            with self.db_manager.get_session() as session:
                product = session.query(Product).filter(Product.id == product_id).first()
                if not product or product.previous_price is None:
                    return False, None, None
                
                has_dropped = product.current_price < product.previous_price
                return has_dropped, product.previous_price, product.current_price
                
        except SQLAlchemyError as e:
            print(f"Database error checking price drop: {e}")
            return False, None, None
    
    def get_products_for_monitoring(self) -> List[Product]:
        """
        Get all active products that should be monitored.
        
        Returns:
            List of active Product instances
        """
        return self.get_all_products(active_only=True)
    
    def _add_price_history(self, session: Session, product_id: int, price: float, source: str):
        """
        Add a price history entry within an existing session.
        
        Args:
            session: Database session
            product_id: Product ID
            price: Price value
            source: Source of the price ('automatic' or 'manual')
        """
        price_history = PriceHistory(
            product_id=product_id,
            price=price,
            recorded_at=datetime.now(),
            source=source
        )
        session.add(price_history)
    
    def get_product_statistics(self) -> dict:
        """
        Get statistics about monitored products.
        
        Returns:
            Dictionary with product statistics
        """
        try:
            with self.db_manager.get_session() as session:
                total_products = session.query(Product).count()
                active_products = session.query(Product).filter(Product.is_active == True).count()
                
                # Get products with recent price drops
                recent_drops = session.query(Product).filter(
                    Product.current_price < Product.previous_price,
                    Product.is_active == True
                ).count()
                
                return {
                    'total_products': total_products,
                    'active_products': active_products,
                    'inactive_products': total_products - active_products,
                    'recent_price_drops': recent_drops
                }
                
        except SQLAlchemyError as e:
            print(f"Database error getting statistics: {e}")
            return {
                'total_products': 0,
                'active_products': 0,
                'inactive_products': 0,
                'recent_price_drops': 0
            }