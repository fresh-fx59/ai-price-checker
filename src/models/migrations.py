"""
Database migration utilities for the Price Monitor application.
"""

import os
import sqlite3
from typing import List, Tuple
from datetime import datetime
from sqlalchemy import text
from .database import DatabaseManager, Base


class MigrationManager:
    """Handles database migrations and schema versioning."""
    
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
        self.migrations_table = 'schema_migrations'
    
    def _ensure_migrations_table(self):
        """Ensure the migrations tracking table exists."""
        with self.db_manager.get_session() as session:
            # Create migrations table if it doesn't exist
            session.execute(text(f"""
                CREATE TABLE IF NOT EXISTS {self.migrations_table} (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    version TEXT UNIQUE NOT NULL,
                    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    description TEXT
                )
            """))
            session.commit()
    
    def get_applied_migrations(self) -> List[str]:
        """Get list of applied migration versions."""
        self._ensure_migrations_table()
        
        with self.db_manager.get_session() as session:
            result = session.execute(text(f"SELECT version FROM {self.migrations_table} ORDER BY version"))
            return [row[0] for row in result.fetchall()]
    
    def apply_migration(self, version: str, description: str, sql_statements: List[str]):
        """
        Apply a migration.
        
        Args:
            version: Migration version (e.g., '001_initial_schema')
            description: Human-readable description
            sql_statements: List of SQL statements to execute
        """
        applied_migrations = self.get_applied_migrations()
        
        if version in applied_migrations:
            print(f"Migration {version} already applied, skipping.")
            return
        
        print(f"Applying migration {version}: {description}")
        
        with self.db_manager.get_session() as session:
            try:
                # Execute migration statements
                for statement in sql_statements:
                    if statement.strip():
                        session.execute(text(statement))
                
                # Record migration as applied
                session.execute(text(f"""
                    INSERT INTO {self.migrations_table} (version, description)
                    VALUES (:version, :description)
                """), {"version": version, "description": description})
                
                session.commit()
                print(f"Migration {version} applied successfully.")
                
            except Exception as e:
                session.rollback()
                print(f"Error applying migration {version}: {e}")
                raise
    
    def run_initial_migration(self):
        """Run the initial database schema migration."""
        # This creates the tables using SQLAlchemy models
        self.db_manager.create_tables()
        
        # Record the initial migration
        self.apply_migration(
            version='001_initial_schema',
            description='Create initial products and price_history tables',
            sql_statements=[]  # Tables already created by SQLAlchemy
        )


def run_migrations(db_manager: DatabaseManager):
    """
    Run all pending migrations.
    
    Args:
        db_manager: Database manager instance
    """
    migration_manager = MigrationManager(db_manager)
    
    # Run initial migration
    migration_manager.run_initial_migration()
    
    print("All migrations completed successfully.")


def reset_database(db_manager: DatabaseManager):
    """
    Reset database by dropping and recreating all tables.
    WARNING: This will delete all data!
    
    Args:
        db_manager: Database manager instance
    """
    print("WARNING: Resetting database - all data will be lost!")
    
    # Drop all tables
    db_manager.drop_tables()
    
    # Recreate tables
    db_manager.create_tables()
    
    # Run migrations
    run_migrations(db_manager)
    
    print("Database reset completed.")