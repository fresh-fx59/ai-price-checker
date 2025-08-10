#!/usr/bin/env python3
"""
Database initialization script for the Price Monitor application.
"""

import sys
import os

# Add the src directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from models.database import get_database_manager
from models.migrations import run_migrations


def main():
    """Initialize the database with tables and run migrations."""
    print("Initializing Price Monitor database...")
    
    # Create database manager
    db_manager = get_database_manager()
    
    # Run migrations
    run_migrations(db_manager)
    
    print("Database initialization completed successfully!")
    print(f"Database location: {db_manager.database_url}")


if __name__ == "__main__":
    main()