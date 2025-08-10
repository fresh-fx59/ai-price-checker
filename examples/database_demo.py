#!/usr/bin/env python3
"""
Demonstration script showing the database models and service layer functionality.
"""

import sys
import os

# Add the project root to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.models.database import get_database_manager
from src.models.migrations import run_migrations
from src.services.product_service import ProductService


def main():
    """Demonstrate database functionality."""
    print("=== Price Monitor Database Demo ===\n")
    
    # Create database manager (uses temporary database for demo)
    print("1. Setting up database...")
    db_manager = get_database_manager("sqlite:///demo_price_monitor.db")
    run_migrations(db_manager)
    print("   ✓ Database initialized\n")
    
    # Create product service
    product_service = ProductService(db_manager)
    
    # Add some sample products
    print("2. Adding sample products...")
    
    product1 = product_service.add_product(
        url="https://example.com/laptop",
        name="Gaming Laptop",
        price=1299.99,
        image_url="https://example.com/laptop.jpg"
    )
    print(f"   ✓ Added: {product1.name} - ${product1.current_price}")
    
    product2 = product_service.add_product(
        url="https://example.com/headphones",
        name="Wireless Headphones",
        price=199.99,
        image_url="https://example.com/headphones.jpg"
    )
    print(f"   ✓ Added: {product2.name} - ${product2.current_price}")
    
    product3 = product_service.add_product(
        url="https://example.com/mouse",
        name="Gaming Mouse",
        price=79.99
    )
    print(f"   ✓ Added: {product3.name} - ${product3.current_price}\n")
    
    # Update some prices
    print("3. Updating prices...")
    
    # Price drop for laptop
    product_service.update_product_price(product1.id, 1199.99, 'automatic')
    print(f"   ✓ {product1.name}: ${product1.current_price} → $1199.99 (price drop!)")
    
    # Price increase for headphones
    product_service.update_product_price(product2.id, 219.99, 'automatic')
    print(f"   ✓ {product2.name}: ${product2.current_price} → $219.99 (price increase)")
    
    # Manual price update for mouse
    product_service.update_product_price(product3.id, 69.99, 'manual')
    print(f"   ✓ {product3.name}: ${product3.current_price} → $69.99 (manual update)\n")
    
    # Show all products
    print("4. Current product list:")
    products = product_service.get_all_products()
    for product in products:
        status = "📉" if product.current_price < (product.previous_price or float('inf')) else "📈" if product.previous_price and product.current_price > product.previous_price else "➡️"
        print(f"   {status} {product.name}")
        print(f"      Current: ${product.current_price}")
        print(f"      Previous: ${product.previous_price or 'N/A'}")
        print(f"      Lowest: ${product.lowest_price}")
        print(f"      URL: {product.url}")
        print()
    
    # Show price history for laptop
    print("5. Price history for Gaming Laptop:")
    history = product_service.get_price_history(product1.id)
    for entry in history:
        print(f"   ${entry.price} - {entry.recorded_at.strftime('%Y-%m-%d %H:%M:%S')} ({entry.source})")
    print()
    
    # Check for price drops
    print("6. Checking for price drops...")
    for product in products:
        has_dropped, prev_price, curr_price = product_service.has_price_dropped(product.id)
        if has_dropped:
            print(f"   🎉 {product.name}: Price dropped from ${prev_price} to ${curr_price}")
        elif prev_price:
            print(f"   📊 {product.name}: No price drop (${prev_price} → ${curr_price})")
    print()
    
    # Show statistics
    print("7. Product statistics:")
    stats = product_service.get_product_statistics()
    print(f"   Total products: {stats['total_products']}")
    print(f"   Active products: {stats['active_products']}")
    print(f"   Recent price drops: {stats['recent_price_drops']}")
    print()
    
    print("=== Demo completed successfully! ===")
    print(f"Database file: demo_price_monitor.db")


if __name__ == "__main__":
    main()