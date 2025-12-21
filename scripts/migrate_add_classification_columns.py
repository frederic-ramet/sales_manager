#!/usr/bin/env python3
"""
Script de migration: Ajoute les colonnes segment et prospect_class à companies.

Ce script:
1. Ajoute les colonnes segment, prospect_class, prospect_class_points, prospect_class_signals
2. Crée les index pour le filtrage
3. (Optionnel) Classifie les entreprises existantes

Usage:
    python scripts/migrate_add_classification_columns.py [--dry-run] [--classify-existing]

Options:
    --dry-run           : Affiche les actions sans les exécuter
    --classify-existing : Classifie les entreprises existantes après migration
"""

import sqlite3
import json
import logging
import argparse
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional

# Ajouter le répertoire parent au path pour les imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Configuration logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Chemins
BASE_DIR = Path(__file__).parent.parent
DB_PATH = BASE_DIR / "data" / "leads.db"


class ClassificationMigration:
    """Migration pour ajouter les colonnes de classification."""

    def __init__(self, db_path: str, dry_run: bool = False):
        self.db_path = db_path
        self.dry_run = dry_run
        self.stats = {
            'columns_added': 0,
            'indexes_created': 0,
            'companies_classified': 0,
            'errors': []
        }

    def run(self, classify_existing: bool = False) -> Dict:
        """
        Exécute la migration.

        Args:
            classify_existing: Si True, classifie les entreprises existantes

        Returns:
            Dict avec statistiques de migration
        """
        logger.info(f"=== Début migration classification {'(DRY RUN)' if self.dry_run else ''} ===")
        logger.info(f"Base de données: {self.db_path}")

        if not Path(self.db_path).exists():
            logger.error(f"Base de données non trouvée: {self.db_path}")
            return self.stats

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row

            # Vérifier si la table companies existe
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='companies'")
            if not cursor.fetchone():
                logger.warning("Table 'companies' non trouvée. Migration annulée.")
                logger.info("Exécutez d'abord: python scripts/migrate_unified_to_companies_contacts.py")
                return self.stats

            # 1. Ajouter les colonnes
            self._add_columns(conn)

            # 2. Créer les index
            self._create_indexes(conn)

            # 3. Classifier les entreprises existantes (optionnel)
            if classify_existing:
                self._classify_existing(conn)

            if not self.dry_run:
                conn.commit()

        logger.info("=== Migration terminée ===")
        logger.info(f"Colonnes ajoutées: {self.stats['columns_added']}")
        logger.info(f"Index créés: {self.stats['indexes_created']}")
        if classify_existing:
            logger.info(f"Entreprises classifiées: {self.stats['companies_classified']}")

        return self.stats

    def _add_columns(self, conn: sqlite3.Connection):
        """Ajoute les nouvelles colonnes à la table companies."""
        cursor = conn.cursor()

        # Obtenir les colonnes existantes
        cursor.execute("PRAGMA table_info(companies)")
        existing_columns = {row[1] for row in cursor.fetchall()}

        columns_to_add = [
            ("segment", "TEXT"),
            ("prospect_class", "TEXT"),
            ("prospect_class_points", "INTEGER"),
            ("prospect_class_signals", "TEXT"),
        ]

        for col_name, col_type in columns_to_add:
            if col_name not in existing_columns:
                sql = f"ALTER TABLE companies ADD COLUMN {col_name} {col_type}"
                logger.info(f"Ajout colonne: {col_name} ({col_type})")

                if not self.dry_run:
                    try:
                        cursor.execute(sql)
                        self.stats['columns_added'] += 1
                    except sqlite3.OperationalError as e:
                        logger.error(f"Erreur ajout colonne {col_name}: {e}")
                        self.stats['errors'].append(str(e))
                else:
                    self.stats['columns_added'] += 1
            else:
                logger.info(f"Colonne {col_name} existe déjà")

    def _create_indexes(self, conn: sqlite3.Connection):
        """Crée les index pour le filtrage."""
        cursor = conn.cursor()

        indexes = [
            ("idx_companies_segment", "companies(segment)"),
            ("idx_companies_prospect_class", "companies(prospect_class)"),
        ]

        for idx_name, idx_def in indexes:
            # Vérifier si l'index existe
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='index' AND name=?",
                (idx_name,)
            )
            if not cursor.fetchone():
                sql = f"CREATE INDEX {idx_name} ON {idx_def}"
                logger.info(f"Création index: {idx_name}")

                if not self.dry_run:
                    try:
                        cursor.execute(sql)
                        self.stats['indexes_created'] += 1
                    except sqlite3.OperationalError as e:
                        logger.error(f"Erreur création index {idx_name}: {e}")
                        self.stats['errors'].append(str(e))
                else:
                    self.stats['indexes_created'] += 1
            else:
                logger.info(f"Index {idx_name} existe déjà")

    def _classify_existing(self, conn: sqlite3.Connection):
        """Classifie les entreprises existantes."""
        try:
            from modules.lead_scraper.scoring import ProspectClassifier
        except ImportError:
            logger.error("Impossible d'importer ProspectClassifier")
            return

        classifier = ProspectClassifier()
        cursor = conn.cursor()

        # Récupérer les entreprises non classifiées
        cursor.execute("""
            SELECT id, company_name, employee_range, revenue_range,
                   ape_code, postal_code
            FROM companies
            WHERE prospect_class IS NULL AND status = 'active'
        """)

        companies = cursor.fetchall()
        logger.info(f"Classification de {len(companies)} entreprises...")

        for row in companies:
            company_data = {
                'employee_range': row['employee_range'],
                'revenue_range': row['revenue_range'],
                'ape_code': row['ape_code'],
                'postal_code': row['postal_code'],
            }

            result = classifier.classify(company_data)

            if not self.dry_run:
                cursor.execute("""
                    UPDATE companies SET
                        prospect_class = ?,
                        prospect_class_points = ?,
                        prospect_class_signals = ?
                    WHERE id = ?
                """, (
                    result['prospect_class'],
                    result['points'],
                    json.dumps(result['signals'], ensure_ascii=False),
                    row['id']
                ))

            self.stats['companies_classified'] += 1

        logger.info(f"Classification terminée: {self.stats['companies_classified']} entreprises")


def main():
    parser = argparse.ArgumentParser(
        description="Migration: Ajoute les colonnes de classification à companies"
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Affiche les actions sans les exécuter'
    )
    parser.add_argument(
        '--classify-existing',
        action='store_true',
        help='Classifie les entreprises existantes après migration'
    )
    parser.add_argument(
        '--db-path',
        type=str,
        default=str(DB_PATH),
        help=f'Chemin vers la base de données (défaut: {DB_PATH})'
    )

    args = parser.parse_args()

    migration = ClassificationMigration(
        db_path=args.db_path,
        dry_run=args.dry_run
    )

    stats = migration.run(classify_existing=args.classify_existing)

    if stats['errors']:
        logger.error(f"Erreurs rencontrées: {len(stats['errors'])}")
        for error in stats['errors']:
            logger.error(f"  - {error}")
        sys.exit(1)

    sys.exit(0)


if __name__ == '__main__':
    main()
