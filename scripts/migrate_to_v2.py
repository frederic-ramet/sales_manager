#!/usr/bin/env python3
"""
Migration Script: Schema V1 → Schema V2

Ce script migre les données de l'ancien schéma (unified_contacts, companies, contacts)
vers le nouveau Schema V2 avec:
- UUID comme clé primaire partout
- Nouvelles colonnes (enrichment, sync, etc.)
- Structure company_uuid pour les contacts

Usage:
    python scripts/migrate_to_v2.py [--dry-run] [--no-backup]

Options:
    --dry-run   : Affiche les actions sans les exécuter
    --no-backup : Ne pas créer de backup
"""

import sqlite3
import uuid
import json
import logging
import argparse
import shutil
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any

# Configuration logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Chemins
BASE_DIR = Path(__file__).parent.parent
DB_PATH = BASE_DIR / "data" / "leads.db"
DB_V2_PATH = BASE_DIR / "data" / "leads_v2.db"
SCHEMA_V2_PATH = BASE_DIR / "database" / "schema_v2.sql"


def generate_uuid() -> str:
    """Génère un UUID v4."""
    return str(uuid.uuid4())


def normalize_company_name(name: str) -> str:
    """Normalise un nom d'entreprise."""
    if not name:
        return ""
    normalized = name.lower().strip()
    for suffix in [' sas', ' sarl', ' sa', ' eurl', ' sasu', ' sci', ' snc']:
        if normalized.endswith(suffix):
            normalized = normalized[:-len(suffix)].strip()
    return normalized


def extract_domain(website: str) -> Optional[str]:
    """Extrait le domaine d'une URL."""
    if not website:
        return None
    website = website.lower().strip()
    for prefix in ['https://', 'http://', 'www.']:
        if website.startswith(prefix):
            website = website[len(prefix):]
    return website.split('/')[0] or None


def map_size(employee_range: str) -> str:
    """Mappe les anciennes valeurs de taille vers le nouveau format."""
    if not employee_range:
        return ""

    employee_range = str(employee_range).strip().lower()

    # Mapping direct
    size_map = {
        '1-10': '1-10',
        '11-50': '11-50',
        '51-200': '51-200',
        '201-500': '201-500',
        '501-1000': '501-1000',
        '1001-5000': '1001-5000',
        '5001-10000': '5001-10000',
        '10000+': '10001+',
        '10001+': '10001+',
    }

    return size_map.get(employee_range, employee_range)


class MigrationToV2:
    """Script de migration vers Schema V2."""

    def __init__(self, old_db_path: str, new_db_path: str, dry_run: bool = False):
        self.old_db_path = old_db_path
        self.new_db_path = new_db_path
        self.dry_run = dry_run
        self.stats = {
            'old_companies': 0,
            'old_contacts': 0,
            'v2_companies_created': 0,
            'v2_contacts_created': 0,
            'v2_interactions_created': 0,
            'errors': []
        }
        # Mapping old_id → new_uuid pour les entreprises
        self.company_mapping: Dict[Any, str] = {}  # old_id or old_uuid → new_uuid

    def run(self, create_backup: bool = True) -> Dict:
        """Exécute la migration complète."""
        logger.info(f"=== Migration vers Schema V2 {'(DRY RUN)' if self.dry_run else ''} ===")
        logger.info(f"Source: {self.old_db_path}")
        logger.info(f"Destination: {self.new_db_path}")

        # 1. Backup
        if create_backup and not self.dry_run:
            self._create_backup()

        # 2. Créer nouvelle base V2
        if not self.dry_run:
            self._create_v2_database()

        # 3. Analyser source
        if not self._analyze_source():
            return self.stats

        # 4. Migrer les données
        self._migrate_companies()
        self._migrate_contacts()
        self._migrate_interactions()

        # 5. Résumé
        self._print_summary()

        return self.stats

    def _create_backup(self):
        """Crée une backup de la base originale."""
        backup_path = Path(self.old_db_path).with_suffix('.db.bak')
        logger.info(f"Création backup: {backup_path}")
        shutil.copy2(self.old_db_path, backup_path)

    def _create_v2_database(self):
        """Crée la nouvelle base de données V2."""
        logger.info("Création de la base V2...")

        # Supprimer si existe déjà
        if Path(self.new_db_path).exists():
            Path(self.new_db_path).unlink()

        # Créer avec schema V2
        with sqlite3.connect(self.new_db_path) as conn:
            if SCHEMA_V2_PATH.exists():
                schema_sql = SCHEMA_V2_PATH.read_text()
                conn.executescript(schema_sql)
                logger.info("  Schema V2 appliqué")
            else:
                logger.error(f"Schema V2 non trouvé: {SCHEMA_V2_PATH}")
                raise FileNotFoundError(str(SCHEMA_V2_PATH))

    def _analyze_source(self) -> bool:
        """Analyse la base source pour déterminer la structure."""
        logger.info("Analyse de la base source...")

        with sqlite3.connect(self.old_db_path) as conn:
            cursor = conn.cursor()

            # Lister les tables
            cursor.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name NOT LIKE 'sqlite_%'
            """)
            tables = [row[0] for row in cursor.fetchall()]
            logger.info(f"  Tables trouvées: {tables}")

            # Compter les données
            if 'companies' in tables:
                cursor.execute("SELECT COUNT(*) FROM companies WHERE status = 'active' OR status IS NULL")
                self.stats['old_companies'] = cursor.fetchone()[0]
                logger.info(f"  Entreprises: {self.stats['old_companies']}")

            if 'contacts' in tables:
                cursor.execute("SELECT COUNT(*) FROM contacts WHERE status = 'active' OR status IS NULL")
                self.stats['old_contacts'] = cursor.fetchone()[0]
                logger.info(f"  Contacts: {self.stats['old_contacts']}")
            elif 'unified_contacts' in tables:
                cursor.execute("SELECT COUNT(*) FROM unified_contacts WHERE status = 'active'")
                self.stats['old_contacts'] = cursor.fetchone()[0]
                logger.info(f"  Contacts (unified): {self.stats['old_contacts']}")

            return self.stats['old_companies'] > 0 or self.stats['old_contacts'] > 0

    def _migrate_companies(self):
        """Migre les entreprises vers V2."""
        logger.info("Migration des entreprises...")

        with sqlite3.connect(self.old_db_path) as old_conn:
            old_conn.row_factory = sqlite3.Row
            old_cursor = old_conn.cursor()

            # Vérifier structure source
            old_cursor.execute("PRAGMA table_info(companies)")
            columns = {row['name'] for row in old_cursor.fetchall()}

            # Déterminer la requête selon les colonnes disponibles
            if 'uuid' in columns:
                # Déjà migré partiellement (V1.5)
                old_cursor.execute("""
                    SELECT * FROM companies
                    WHERE status = 'active' OR status IS NULL
                """)
            else:
                # Ancien format avec ID
                old_cursor.execute("""
                    SELECT * FROM companies
                    WHERE status = 'active' OR status IS NULL
                """)

            companies = old_cursor.fetchall()

            if self.dry_run:
                self.stats['v2_companies_created'] = len(companies)
                logger.info(f"  [DRY RUN] {len(companies)} entreprises seraient migrées")
                # Créer le mapping pour contacts
                for company in companies:
                    old_key = company.get('uuid') or company.get('id')
                    self.company_mapping[old_key] = generate_uuid()
                return

            with sqlite3.connect(self.new_db_path) as new_conn:
                new_cursor = new_conn.cursor()

                for company in companies:
                    try:
                        # Générer nouvel UUID
                        new_uuid = generate_uuid()

                        # Mapper ancienne clé vers nouvelle
                        old_key = company.get('uuid') or company.get('id')
                        self.company_mapping[old_key] = new_uuid

                        # Mapper les champs
                        new_cursor.execute("""
                            INSERT INTO companies (
                                uuid, siren, siret, hubspot_company_id,
                                name, domain, legal_form,
                                hq_address, hq_city, hq_state, hq_postal_code, hq_country,
                                ape_code, ape_label, industry, description,
                                size, size_exact, revenue, revenue_range,
                                founded_date,
                                source, source_file, created_at, updated_at,
                                status, synced_to_hubspot, last_sync_hubspot,
                                total_contacts
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            new_uuid,
                            company.get('siren'),
                            company.get('siret'),
                            company.get('hubspot_company_id'),
                            company.get('company_name') or company.get('name'),
                            extract_domain(company.get('website')) or company.get('domain'),
                            company.get('legal_form'),
                            company.get('address') or company.get('hq_address'),
                            company.get('city') or company.get('hq_city'),
                            company.get('region') or company.get('hq_state'),
                            company.get('postal_code') or company.get('hq_postal_code'),
                            company.get('country') or company.get('hq_country') or 'France',
                            company.get('ape_code'),
                            company.get('ape_label'),
                            company.get('industry'),
                            company.get('description'),
                            map_size(company.get('employee_range') or company.get('size')),
                            company.get('size_exact'),
                            company.get('revenue'),
                            company.get('revenue_range'),
                            company.get('founded_date'),
                            company.get('source', 'migration'),
                            company.get('source_file'),
                            company.get('created_at') or datetime.now().isoformat(),
                            company.get('updated_at') or datetime.now().isoformat(),
                            'active',
                            company.get('synced_to_hubspot') or 0,
                            company.get('last_sync_hubspot'),
                            company.get('total_contacts') or 0
                        ))
                        self.stats['v2_companies_created'] += 1

                    except Exception as e:
                        self.stats['errors'].append(f"Company {old_key}: {e}")
                        logger.error(f"  Erreur company: {e}")

                new_conn.commit()

        logger.info(f"  {self.stats['v2_companies_created']} entreprises migrées")

    def _migrate_contacts(self):
        """Migre les contacts vers V2."""
        logger.info("Migration des contacts...")

        with sqlite3.connect(self.old_db_path) as old_conn:
            old_conn.row_factory = sqlite3.Row
            old_cursor = old_conn.cursor()

            # Vérifier quelle table de contacts existe
            old_cursor.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name IN ('contacts', 'unified_contacts')
            """)
            tables = [row[0] for row in old_cursor.fetchall()]

            if 'contacts' in tables:
                old_cursor.execute("""
                    SELECT * FROM contacts
                    WHERE status = 'active' OR status IS NULL
                """)
            elif 'unified_contacts' in tables:
                old_cursor.execute("""
                    SELECT * FROM unified_contacts
                    WHERE status = 'active'
                """)
            else:
                logger.warning("  Aucune table de contacts trouvée")
                return

            contacts = old_cursor.fetchall()

            if self.dry_run:
                self.stats['v2_contacts_created'] = len(contacts)
                logger.info(f"  [DRY RUN] {len(contacts)} contacts seraient migrés")
                return

            with sqlite3.connect(self.new_db_path) as new_conn:
                new_cursor = new_conn.cursor()

                for contact in contacts:
                    try:
                        # Nouvel UUID
                        new_uuid = generate_uuid()

                        # Mapper company_id ou company_uuid vers le nouveau UUID
                        old_company_key = contact.get('company_uuid') or contact.get('company_id')
                        new_company_uuid = self.company_mapping.get(old_company_key)

                        new_cursor.execute("""
                            INSERT INTO contacts (
                                uuid, company_uuid, hubspot_contact_id, getsales_uuid,
                                firstname, lastname, linkedin_url,
                                email, email_verified, email_secondary, phone, mobile,
                                job_title, seniority, department,
                                city, state, country,
                                source, source_file, campaign_id, project_name, search_name,
                                created_at, updated_at,
                                status, synced_to_hubspot, last_sync_hubspot,
                                notes
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            new_uuid,
                            new_company_uuid,
                            contact.get('hubspot_contact_id'),
                            contact.get('getsales_uuid'),
                            contact.get('firstname'),
                            contact.get('lastname'),
                            contact.get('linkedin_url'),
                            contact.get('email'),
                            contact.get('email_verified') or 0,
                            contact.get('email_secondary'),
                            contact.get('phone'),
                            contact.get('mobile'),
                            contact.get('job_title'),
                            contact.get('seniority'),
                            contact.get('department'),
                            contact.get('city'),
                            contact.get('state') or contact.get('region'),
                            contact.get('country') or 'France',
                            contact.get('source', 'migration'),
                            contact.get('source_file'),
                            contact.get('campaign_id'),
                            contact.get('project_name'),
                            contact.get('search_name'),
                            contact.get('created_at') or datetime.now().isoformat(),
                            contact.get('updated_at') or datetime.now().isoformat(),
                            'active',
                            contact.get('synced_to_hubspot') or 0,
                            contact.get('last_sync_hubspot'),
                            contact.get('notes')
                        ))
                        self.stats['v2_contacts_created'] += 1

                    except Exception as e:
                        self.stats['errors'].append(f"Contact {contact.get('email')}: {e}")
                        logger.error(f"  Erreur contact: {e}")

                new_conn.commit()

        logger.info(f"  {self.stats['v2_contacts_created']} contacts migrés")

    def _migrate_interactions(self):
        """Migre les interactions si elles existent."""
        logger.info("Migration des interactions...")

        with sqlite3.connect(self.old_db_path) as old_conn:
            old_conn.row_factory = sqlite3.Row
            old_cursor = old_conn.cursor()

            # Vérifier si table interactions existe
            old_cursor.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='interactions'
            """)
            if not old_cursor.fetchone():
                logger.info("  Aucune table interactions trouvée")
                return

            old_cursor.execute("SELECT * FROM interactions")
            interactions = old_cursor.fetchall()

            if self.dry_run:
                self.stats['v2_interactions_created'] = len(interactions)
                logger.info(f"  [DRY RUN] {len(interactions)} interactions seraient migrées")
                return

            logger.info(f"  {len(interactions)} interactions à migrer")
            # Note: Migration complète des interactions nécessiterait un mapping contact_uuid
            self.stats['v2_interactions_created'] = 0  # À implémenter si nécessaire

    def _print_summary(self):
        """Affiche le résumé de la migration."""
        print("\n" + "=" * 60)
        print("RÉSUMÉ DE LA MIGRATION V2")
        print("=" * 60)
        print(f"Source:")
        print(f"  Entreprises:    {self.stats['old_companies']}")
        print(f"  Contacts:       {self.stats['old_contacts']}")
        print()
        print(f"Destination (V2):")
        print(f"  Entreprises:    {self.stats['v2_companies_created']}")
        print(f"  Contacts:       {self.stats['v2_contacts_created']}")
        print(f"  Interactions:   {self.stats['v2_interactions_created']}")
        print()
        print(f"Erreurs:          {len(self.stats['errors'])}")

        if self.stats['errors']:
            print("\nErreurs rencontrées:")
            for err in self.stats['errors'][:10]:
                print(f"  - {err}")
            if len(self.stats['errors']) > 10:
                print(f"  ... et {len(self.stats['errors']) - 10} autres")

        print("=" * 60)

        if not self.dry_run:
            print(f"\n*** Nouvelle base créée: {self.new_db_path}")
            print(f"*** Pour utiliser V2, copiez leads_v2.db vers leads.db ***")


def main():
    parser = argparse.ArgumentParser(
        description="Migration Schema V1 → Schema V2"
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Affiche les actions sans les exécuter'
    )
    parser.add_argument(
        '--no-backup',
        action='store_true',
        help='Ne pas créer de backup'
    )
    parser.add_argument(
        '--source',
        type=str,
        default=str(DB_PATH),
        help=f'Base de données source (défaut: {DB_PATH})'
    )
    parser.add_argument(
        '--dest',
        type=str,
        default=str(DB_V2_PATH),
        help=f'Base de données destination (défaut: {DB_V2_PATH})'
    )

    args = parser.parse_args()

    # Vérifier que la source existe
    if not Path(args.source).exists():
        logger.error(f"Base de données source non trouvée: {args.source}")
        return 1

    # Vérifier que le schema V2 existe
    if not SCHEMA_V2_PATH.exists():
        logger.error(f"Schema V2 non trouvé: {SCHEMA_V2_PATH}")
        return 1

    # Exécuter la migration
    migration = MigrationToV2(args.source, args.dest, dry_run=args.dry_run)
    stats = migration.run(create_backup=not args.no_backup)

    # Code retour
    if len(stats['errors']) > 0:
        return 1
    return 0


if __name__ == "__main__":
    exit(main())
