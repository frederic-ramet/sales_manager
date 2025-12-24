#!/usr/bin/env python3
"""
Database Initialization Script - Schema V2

Usage:
    python database/init_db_v2.py [--reset]

Options:
    --reset     Supprime la base existante et recrée de zéro

Ce script:
1. Crée la base de données si elle n'existe pas
2. Applique le schema v2
3. Optionnel: reset complet avec --reset
"""

import sqlite3
import argparse
import logging
from pathlib import Path
from datetime import datetime

# Configuration
DB_PATH = Path(__file__).parent.parent / "data" / "leads.db"
SCHEMA_PATH = Path(__file__).parent / "schema_v2.sql"

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def reset_database():
    """Supprime la base de données existante."""
    if DB_PATH.exists():
        # Backup avant suppression
        backup_path = DB_PATH.with_suffix(f'.db.backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}')
        DB_PATH.rename(backup_path)
        logger.info(f"Base de données sauvegardée: {backup_path}")
    logger.info("Base de données réinitialisée")


def init_database():
    """Initialise la base de données avec le schema v2."""
    # Créer le dossier data si nécessaire
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    # Lire le schema SQL
    if not SCHEMA_PATH.exists():
        logger.error(f"Schema non trouvé: {SCHEMA_PATH}")
        return False

    schema_sql = SCHEMA_PATH.read_text()

    # Appliquer le schema
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()

            # Exécuter le schema (plusieurs statements)
            cursor.executescript(schema_sql)

            conn.commit()
            logger.info(f"Schema v2 appliqué avec succès: {DB_PATH}")

            # Vérifier les tables créées
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
            tables = [row[0] for row in cursor.fetchall()]
            logger.info(f"Tables créées: {', '.join(tables)}")

            cursor.execute("SELECT name FROM sqlite_master WHERE type='view' ORDER BY name")
            views = [row[0] for row in cursor.fetchall()]
            logger.info(f"Vues créées: {', '.join(views)}")

            return True

    except Exception as e:
        logger.error(f"Erreur lors de l'initialisation: {e}")
        return False


def verify_schema():
    """Vérifie que le schema est correctement appliqué."""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()

            # Vérifier les tables principales
            expected_tables = ['companies', 'contacts', 'engagements', 'homonym_groups', 'sync_metadata', 'import_history']
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            actual_tables = {row[0] for row in cursor.fetchall()}

            missing = set(expected_tables) - actual_tables
            if missing:
                logger.error(f"Tables manquantes: {missing}")
                return False

            # Vérifier quelques colonnes clés
            cursor.execute("PRAGMA table_info(companies)")
            company_columns = {row[1] for row in cursor.fetchall()}
            expected_company_cols = {'uuid', 'siren', 'name', 'domain', 'hubspot_company_id', 'status'}
            if not expected_company_cols.issubset(company_columns):
                logger.error(f"Colonnes manquantes dans companies")
                return False

            cursor.execute("PRAGMA table_info(contacts)")
            contact_columns = {row[1] for row in cursor.fetchall()}
            expected_contact_cols = {'uuid', 'company_uuid', 'firstname', 'lastname', 'email', 'linkedin_url', 'status'}
            if not expected_contact_cols.issubset(contact_columns):
                logger.error(f"Colonnes manquantes dans contacts")
                return False

            logger.info("✅ Schema v2 vérifié avec succès")
            return True

    except Exception as e:
        logger.error(f"Erreur lors de la vérification: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description='Initialize database with schema v2')
    parser.add_argument('--reset', action='store_true', help='Reset database (delete and recreate)')
    args = parser.parse_args()

    print("=" * 60)
    print("DATABASE INITIALIZATION - SCHEMA V2")
    print("=" * 60)

    if args.reset:
        print("\n⚠️  MODE RESET: La base existante sera supprimée!")
        confirm = input("Confirmer? (oui/non): ")
        if confirm.lower() != 'oui':
            print("Annulé.")
            return
        reset_database()

    print(f"\n📁 Database path: {DB_PATH}")
    print(f"📄 Schema path: {SCHEMA_PATH}")

    if init_database():
        if verify_schema():
            print("\n✅ Base de données initialisée avec succès!")
            print("\nProchaines étapes:")
            print("  1. Adapter les managers (company_manager, contact_manager)")
            print("  2. Créer interaction_manager")
            print("  3. Tester avec un import CSV")
        else:
            print("\n❌ Erreur de vérification du schema")
    else:
        print("\n❌ Erreur lors de l'initialisation")


if __name__ == "__main__":
    main()
