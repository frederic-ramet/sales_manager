#!/usr/bin/env python3
"""
Migration Script: V2 → V2.1

Adds new fields for Pipeline V2.1:
- companies: tier, owner, source_tag
- contacts: qualification_status, source_tag
- Rename interactions → engagements

Usage:
    python database/migrate_v2_to_v2.1.py
"""

import sqlite3
import logging
from pathlib import Path
from datetime import datetime

# Configuration
DB_PATH = Path(__file__).parent.parent / "data" / "leads.db"

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def get_existing_columns(cursor, table_name: str) -> set:
    """Get existing columns for a table."""
    cursor.execute(f"PRAGMA table_info({table_name})")
    return {row[1] for row in cursor.fetchall()}


def column_exists(cursor, table_name: str, column_name: str) -> bool:
    """Check if a column exists in a table."""
    columns = get_existing_columns(cursor, table_name)
    return column_name in columns


def table_exists(cursor, table_name: str) -> bool:
    """Check if a table exists."""
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
    return cursor.fetchone() is not None


def migrate():
    """Run the migration."""
    if not DB_PATH.exists():
        logger.error(f"Database not found: {DB_PATH}")
        return False

    logger.info(f"Starting migration on: {DB_PATH}")

    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()

            # =========================================================
            # COMPANIES: Add new columns
            # =========================================================
            logger.info("Migrating companies table...")

            # Add tier column
            if not column_exists(cursor, 'companies', 'tier'):
                cursor.execute("""
                    ALTER TABLE companies
                    ADD COLUMN tier TEXT DEFAULT 'unclassified'
                """)
                logger.info("  + Added column: tier")
            else:
                logger.info("  - Column tier already exists")

            # Add owner column
            if not column_exists(cursor, 'companies', 'owner'):
                cursor.execute("""
                    ALTER TABLE companies
                    ADD COLUMN owner TEXT
                """)
                logger.info("  + Added column: owner")
            else:
                logger.info("  - Column owner already exists")

            # Add source_tag column
            if not column_exists(cursor, 'companies', 'source_tag'):
                cursor.execute("""
                    ALTER TABLE companies
                    ADD COLUMN source_tag TEXT
                """)
                logger.info("  + Added column: source_tag")
            else:
                logger.info("  - Column source_tag already exists")

            # =========================================================
            # CONTACTS: Add new columns
            # =========================================================
            logger.info("Migrating contacts table...")

            # Add qualification_status column
            if not column_exists(cursor, 'contacts', 'qualification_status'):
                cursor.execute("""
                    ALTER TABLE contacts
                    ADD COLUMN qualification_status TEXT DEFAULT 'contact'
                """)
                logger.info("  + Added column: qualification_status")
            else:
                logger.info("  - Column qualification_status already exists")

            # Add source_tag column
            if not column_exists(cursor, 'contacts', 'source_tag'):
                cursor.execute("""
                    ALTER TABLE contacts
                    ADD COLUMN source_tag TEXT
                """)
                logger.info("  + Added column: source_tag")
            else:
                logger.info("  - Column source_tag already exists")

            # =========================================================
            # RENAME: interactions → engagements
            # =========================================================
            logger.info("Checking interactions → engagements rename...")

            if table_exists(cursor, 'interactions') and not table_exists(cursor, 'engagements'):
                cursor.execute("ALTER TABLE interactions RENAME TO engagements")
                logger.info("  + Renamed table: interactions → engagements")

                # Update total_interactions → total_engagements in companies
                # (keeping total_interactions for backwards compat, just adding alias)
            elif table_exists(cursor, 'engagements'):
                logger.info("  - Table engagements already exists")
            elif not table_exists(cursor, 'interactions'):
                # Create engagements table if neither exists
                logger.info("  - Creating engagements table from scratch")
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS engagements (
                        uuid TEXT PRIMARY KEY,
                        contact_uuid TEXT NOT NULL,
                        hubspot_engagement_id TEXT,
                        getsales_message_id TEXT,
                        type TEXT NOT NULL,
                        direction TEXT,
                        channel TEXT,
                        subject TEXT,
                        content TEXT,
                        content_html TEXT,
                        interaction_date TIMESTAMP NOT NULL,
                        duration_minutes INTEGER,
                        campaign_id TEXT,
                        sequence_name TEXT,
                        sequence_step INTEGER,
                        outcome TEXT,
                        source TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (contact_uuid) REFERENCES contacts(uuid) ON DELETE CASCADE
                    )
                """)
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_engagements_contact ON engagements(contact_uuid)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_engagements_date ON engagements(interaction_date)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_engagements_type ON engagements(type)")
                logger.info("  + Created table: engagements")

            # =========================================================
            # NEW INDEXES
            # =========================================================
            logger.info("Creating new indexes...")

            cursor.execute("CREATE INDEX IF NOT EXISTS idx_companies_tier ON companies(tier)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_companies_owner ON companies(owner)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_contacts_qualification ON contacts(qualification_status)")
            logger.info("  + Created indexes for tier, owner, qualification_status")

            # =========================================================
            # COMMIT
            # =========================================================
            conn.commit()
            logger.info("Migration completed successfully!")

            # Verify
            logger.info("\nVerification:")
            for table in ['companies', 'contacts']:
                cols = get_existing_columns(cursor, table)
                logger.info(f"  {table}: {len(cols)} columns")

            if table_exists(cursor, 'engagements'):
                logger.info("  engagements: table exists")

            return True

    except Exception as e:
        logger.error(f"Migration failed: {e}")
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("MIGRATION V2 → V2.1")
    print("=" * 60)

    if migrate():
        print("\n✅ Migration réussie!")
    else:
        print("\n❌ Migration échouée!")
