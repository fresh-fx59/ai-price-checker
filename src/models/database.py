"""
Database models and initialization utilities for the Price Monitor application.
"""

from datetime import datetime
from typing import Optional, List
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Boolean, Text, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship, Session
from sqlalchemy.sql import func
import os

Base = declarative_base()


class Product(Base):
    """Product model representing a monitored product."""
    
    __tablename__ = 'products'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    url = Column(Text, unique=True, nullable=False)
    name = Column(String(500), nullable=False)
    current_price = Column(Float, nullable=False)
    previous_price = Column(Float, nullable=True)
    lowest_price = Column(Float, nullable=False)
    image_url = Column(Text, nullable=True)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    last_checked = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Relationship to price history
    price_history = relationship("PriceHistory", back_populates="product", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Product(id={self.id}, name='{self.name}', current_price={self.current_price})>"


class PriceHistory(Base):
    """Price history model for tracking price changes over time."""
    
    __tablename__ = 'price_history'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(Integer, ForeignKey('products.id'), nullable=False)
    price = Column(Float, nullable=False)
    recorded_at = Column(DateTime, default=func.now(), nullable=False)
    source = Column(String(20), nullable=False)  # 'automatic' or 'manual'
    
    # Relationship to product
    product = relationship("Product", back_populates="price_history")
    
    def __repr__(self):
        return f"<PriceHistory(id={self.id}, product_id={self.product_id}, price={self.price}, source='{self.source}')>"


class DatabaseManager:
    """Database connection and initialization manager."""
    
    def __init__(self, database_url: str = None):
        """
        Initialize database manager.
        
        Args:
            database_url: Database connection URL. If None, uses SQLite with default path.
        """
        if database_url is None:
            # Default to SQLite database in data directory
            data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data')
            os.makedirs(data_dir, exist_ok=True)
            database_url = f"sqlite:///{os.path.join(data_dir, 'price_monitor.db')}"
        
        self.database_url = database_url
        self.engine = create_engine(database_url, echo=False)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
    
    def create_tables(self):
        """Create all database tables."""
        Base.metadata.create_all(bind=self.engine)
    
    def drop_tables(self):
        """Drop all database tables. Use with caution!"""
        Base.metadata.drop_all(bind=self.engine)
    
    def get_session(self) -> Session:
        """Get a new database session."""
        return self.SessionLocal()
    
    def init_database(self):
        """Initialize database with tables and any required initial data."""
        self.create_tables()
        print(f"Database initialized at: {self.database_url}")


def get_database_manager(database_url: str = None) -> DatabaseManager:
    """
    Factory function to get a database manager instance.
    
    Args:
        database_url: Database connection URL
        
    Returns:
        DatabaseManager instance
    """
    return DatabaseManager(database_url)