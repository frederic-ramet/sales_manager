#!/usr/bin/env python3
"""
Script de migration: unified_contacts → companies + contacts

Ce script:
1. Crée les nouvelles tables (companies, contacts)
2. Extrait les entreprises uniques depuis unified_contacts
3. Migre les contacts en les liant aux entreprises
4. Crée la vue de compatibilité legacy
5. Renomme l'ancienne table en backup

Usage:
    python scripts/migrate_unified_to_companies_contacts.py [--dry-run] [--no-backup]

Options:
    --dry-run   : Affiche les actions sans les exécuter
    --no-backup : Ne pas créer de backup (non recommandé)
"""

import sqlite3
import uuid
import json
import logging
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple

# Configuration logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Chemins
BASE_DIR = Path(__file__).parent.parent
DB_PATH = BASE_DIR / "data" / "leads.db"
MIGRATIONS_DIR = BASE_DIR / "migrations"


def generate_uuid() -> str:
    """Génère un UUID v4."""
    return str(uuid.uuid4())


def normalize_company_name(name: str) -> str:
    """Normalise un nom d'entreprise pour le groupement."""
    if not name:
        return ""
    # Lowercase, trim, supprimer formes juridiques courantes
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
    # Supprimer protocole
    for prefix in ['https://', 'http://', 'www.']:
        if website.startswith(prefix):
            website = website[len(prefix):]
    # Supprimer path
    website = website.split('/')[0]
    return website if website else None


class MigrationScript:
    """Script de migration unified_contacts → companies + contacts."""

    def __init__(self, db_path: str, dry_run: bool = False):
        self.db_path = db_path
        self.dry_run = dry_run
        self.stats = {
            'unified_contacts_count': 0,
            'companies_created': 0,
            'contacts_migrated': 0,
            'orphan_contacts': 0,
            'errors': []
        }

    def run(self, create_backup: bool = True) -> Dict:
        """
        Exécute la migration complète.

        Args:
            create_backup: Si True, crée une backup de unified_contacts

        Returns:
            Dict avec statistiques de migration
        """
        logger.info(f"=== Début migration {'(DRY RUN)' if self.dry_run else ''} ===")
        logger.info(f"Base de données: {self.db_path}")

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row

            # 0. Vérifier état actuel
            if not self._check_prerequisites(conn):
                return self.stats

            # 1. Compter contacts actuels
            self.stats['unified_contacts_count'] = self._count_unified_contacts(conn)
            logger.info(f"Contacts actuels dans unified_contacts: {self.stats['unified_contacts_count']}")

            if self.stats['unified_contacts_count'] == 0:
                logger.warning("Aucun contact à migrer!")
                return self.stats

            # 2. Créer nouvelles tables
            self._create_new_tables(conn)

            # 3. Extraire et insérer les entreprises
            company_mapping = self._migrate_companies(conn)
            logger.info(f"Entreprises créées: {self.stats['companies_created']}")

            # 4. Migrer les contacts
            self._migrate_contacts(conn, company_mapping)
            logger.info(f"Contacts migrés: {self.stats['contacts_migrated']}")
            logger.info(f"Contacts orphelins (sans entreprise): {self.stats['orphan_contacts']}")

            # 5. Mettre à jour stats companies
            self._update_company_stats(conn)

            # 6. Créer backup et renommer tables
            if create_backup and not self.dry_run:
                self._finalize_migration(conn)

            if not self.dry_run:
                conn.commit()
                logger.info("Migration commitée avec succès!")
            else:
                logger.info("DRY RUN - Aucune modification effectuée")

        logger.info(f"=== Fin migration ===")
        self._print_summary()

        return self.stats

    def _check_prerequisites(self, conn: sqlite3.Connection) -> bool:
        """Vérifie les prérequis pour la migration."""
        cursor = conn.cursor()

        # Vérifier que unified_contacts existe
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='unified_contacts'
        """)
        if not cursor.fetchone():
            logger.error("Table unified_contacts non trouvée!")
            return False

        # Vérifier si migration déjà faite
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='companies'
        """)
        if cursor.fetchone():
            cursor.execute("SELECT COUNT(*) FROM companies")
            count = cursor.fetchone()[0]
            if count > 0:
                logger.warning(f"Table companies existe déjà avec {count} entrées!")
                logger.warning("Utilisez --force pour refaire la migration")
                return False

        return True

    def _count_unified_contacts(self, conn: sqlite3.Connection) -> int:
        """Compte les contacts dans unified_contacts."""
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM unified_contacts WHERE status = 'active'")
        return cursor.fetchone()[0]

    def _create_new_tables(self, conn: sqlite3.Connection):
        """Crée les nouvelles tables companies et contacts."""
        logger.info("Création des nouvelles tables...")

        if self.dry_run:
            logger.info("  [DRY RUN] Tables seraient créées")
            return

        # Lire et exécuter le script SQL companies
        companies_sql = MIGRATIONS_DIR / "001_create_companies.sql"
        if companies_sql.exists():
            conn.executescript(companies_sql.read_text())
            logger.info("  Table companies créée")

        # Lire et exécuter le script SQL contacts
        contacts_sql = MIGRATIONS_DIR / "002_create_contacts.sql"
        if contacts_sql.exists():
            conn.executescript(contacts_sql.read_text())
            logger.info("  Table contacts créée")

    def _migrate_companies(self, conn: sqlite3.Connection) -> Dict[str, int]:
        """
        Extrait et insère les entreprises uniques.

        Returns:
            Mapping {clé_unique: company_id}
        """
        logger.info("Extraction des entreprises uniques...")
        cursor = conn.cursor()

        # Stratégie: Grouper par SIREN si présent, sinon par (company_name, website)
        company_mapping = {}  # {siren ou "name|website": company_id}

        # 1. Entreprises avec SIREN (prioritaire)
        cursor.execute("""
            SELECT
                siren,
                company_name,
                ape_code,
                ape_label,
                legal_form,
                address,
                postal_code,
                city,
                region,
                country,
                employee_range,
                revenue_range,
                website,
                source,
                campaign_id,
                MIN(created_at) as created_at,
                MAX(updated_at) as updated_at
            FROM unified_contacts
            WHERE siren IS NOT NULL AND siren != '' AND status = 'active'
            GROUP BY siren
        """)

        siren_companies = cursor.fetchall()
        logger.info(f"  {len(siren_companies)} entreprises avec SIREN")

        for row in siren_companies:
            if self.dry_run:
                self.stats['companies_created'] += 1
                company_mapping[row['siren']] = self.stats['companies_created']
                continue

            company_uuid = generate_uuid()
            cursor.execute("""
                INSERT INTO companies (
                    uuid, siren, company_name, ape_code, ape_label, legal_form,
                    address, postal_code, city, region, country,
                    employee_range, revenue_range, website,
                    source, campaign_id, created_at, updated_at, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active')
            """, (
                company_uuid,
                row['siren'],
                row['company_name'],
                row['ape_code'],
                row['ape_label'],
                row['legal_form'],
                row['address'],
                row['postal_code'],
                row['city'],
                row['region'],
                row['country'] or 'FR',
                row['employee_range'],
                row['revenue_range'],
                row['website'],
                row['source'],
                row['campaign_id'],
                row['created_at'],
                row['updated_at']
            ))
            company_id = cursor.lastrowid
            company_mapping[row['siren']] = company_id
            self.stats['companies_created'] += 1

        # 2. Entreprises sans SIREN (GetSales, etc.) - grouper par nom+website
        cursor.execute("""
            SELECT
                company_name,
                website,
                ape_code,
                ape_label,
                legal_form,
                address,
                postal_code,
                city,
                region,
                country,
                employee_range,
                revenue_range,
                source,
                campaign_id,
                MIN(created_at) as created_at,
                MAX(updated_at) as updated_at
            FROM unified_contacts
            WHERE (siren IS NULL OR siren = '')
              AND company_name IS NOT NULL AND company_name != ''
              AND status = 'active'
            GROUP BY LOWER(company_name), COALESCE(website, '')
        """)

        no_siren_companies = cursor.fetchall()
        logger.info(f"  {len(no_siren_companies)} entreprises sans SIREN")

        for row in no_siren_companies:
            # Créer clé unique basée sur nom normalisé + domain
            name_norm = normalize_company_name(row['company_name'])
            domain = extract_domain(row['website']) or ''
            unique_key = f"{name_norm}|{domain}"

            if unique_key in company_mapping:
                continue  # Déjà traité

            if self.dry_run:
                self.stats['companies_created'] += 1
                company_mapping[unique_key] = self.stats['companies_created']
                continue

            company_uuid = generate_uuid()
            cursor.execute("""
                INSERT INTO companies (
                    uuid, siren, company_name, ape_code, ape_label, legal_form,
                    address, postal_code, city, region, country,
                    employee_range, revenue_range, website,
                    source, campaign_id, created_at, updated_at, status
                ) VALUES (?, NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active')
            """, (
                company_uuid,
                row['company_name'],
                row['ape_code'],
                row['ape_label'],
                row['legal_form'],
                row['address'],
                row['postal_code'],
                row['city'],
                row['region'],
                row['country'] or 'FR',
                row['employee_range'],
                row['revenue_range'],
                row['website'],
                row['source'],
                row['campaign_id'],
                row['created_at'],
                row['updated_at']
            ))
            company_id = cursor.lastrowid
            company_mapping[unique_key] = company_id
            self.stats['companies_created'] += 1

        return company_mapping

    def _migrate_contacts(self, conn: sqlite3.Connection, company_mapping: Dict[str, int]):
        """Migre les contacts vers la nouvelle table."""
        logger.info("Migration des contacts...")
        cursor = conn.cursor()

        # Récupérer tous les contacts actifs
        cursor.execute("""
            SELECT * FROM unified_contacts WHERE status = 'active'
        """)

        contacts = cursor.fetchall()
        logger.info(f"  {len(contacts)} contacts à migrer")

        for row in contacts:
            # Trouver le company_id correspondant
            company_id = None

            if row['siren']:
                company_id = company_mapping.get(row['siren'])
            elif row['company_name']:
                name_norm = normalize_company_name(row['company_name'])
                domain = extract_domain(row['website']) or ''
                unique_key = f"{name_norm}|{domain}"
                company_id = company_mapping.get(unique_key)

            if company_id is None and row['company_name']:
                self.stats['orphan_contacts'] += 1

            if self.dry_run:
                self.stats['contacts_migrated'] += 1
                continue

            # Insérer dans nouvelle table contacts
            try:
                cursor.execute("""
                    INSERT INTO contacts (
                        uuid, company_id, getsales_uuid, hubspot_contact_id,
                        firstname, lastname, email, phone, mobile,
                        job_title, linkedin_url, linkedin_headline,
                        prospection_status, messages_sent, messages_received, last_interaction_at,
                        synced_to_hubspot, last_sync_hubspot,
                        source, campaign_id, created_at, updated_at, status,
                        notes, raw_data
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    row['uuid'],
                    company_id,
                    row['getsales_uuid'],
                    row['hubspot_contact_id'],
                    row['firstname'],
                    row['lastname'],
                    row['email'],
                    row['phone'],
                    row['mobile'],
                    row['job_title'],
                    row['linkedin_url'],
                    row['linkedin_headline'],
                    row['prospection_status'],
                    row['messages_sent'] or 0,
                    row['messages_received'] or 0,
                    row['last_interaction_at'],
                    row['synced_to_hubspot'] or 0,
                    row['last_sync_hubspot'],
                    row['source'],
                    row['campaign_id'],
                    row['created_at'],
                    row['updated_at'],
                    row['status'],
                    row['notes'],
                    row['raw_data']
                ))
                self.stats['contacts_migrated'] += 1
            except sqlite3.IntegrityError as e:
                # Doublon email/linkedin - log et skip
                self.stats['errors'].append(f"Contact {row['uuid']}: {e}")
                logger.warning(f"  Doublon ignoré: {row['email']} - {e}")

    def _update_company_stats(self, conn: sqlite3.Connection):
        """Met à jour les stats agrégées des companies."""
        if self.dry_run:
            return

        logger.info("Mise à jour des statistiques entreprises...")
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE companies SET
                total_contacts = (
                    SELECT COUNT(*) FROM contacts WHERE contacts.company_id = companies.id
                ),
                total_messages_sent = (
                    SELECT COALESCE(SUM(messages_sent), 0) FROM contacts WHERE contacts.company_id = companies.id
                ),
                total_messages_received = (
                    SELECT COALESCE(SUM(messages_received), 0) FROM contacts WHERE contacts.company_id = companies.id
                ),
                last_contact_interaction_at = (
                    SELECT MAX(last_interaction_at) FROM contacts WHERE contacts.company_id = companies.id
                )
        """)

    def _finalize_migration(self, conn: sqlite3.Connection):
        """Crée backup et finalise la migration."""
        logger.info("Finalisation de la migration...")
        cursor = conn.cursor()

        # Renommer unified_contacts en backup
        cursor.execute("""
            ALTER TABLE unified_contacts RENAME TO unified_contacts_backup
        """)
        logger.info("  unified_contacts → unified_contacts_backup")

        # Créer vue unified_contacts pour compatibilité temporaire
        # (déjà créée dans 002_create_contacts.sql comme unified_contacts_legacy)
        # On crée une vue unified_contacts qui pointe vers unified_contacts_legacy
        cursor.execute("""
            CREATE VIEW IF NOT EXISTS unified_contacts AS
            SELECT * FROM unified_contacts_legacy
        """)
        logger.info("  Vue unified_contacts créée pour compatibilité")

    def _print_summary(self):
        """Affiche le résumé de la migration."""
        print("\n" + "=" * 50)
        print("RÉSUMÉ DE LA MIGRATION")
        print("=" * 50)
        print(f"Contacts source:        {self.stats['unified_contacts_count']}")
        print(f"Entreprises créées:     {self.stats['companies_created']}")
        print(f"Contacts migrés:        {self.stats['contacts_migrated']}")
        print(f"Contacts orphelins:     {self.stats['orphan_contacts']}")
        print(f"Erreurs:                {len(self.stats['errors'])}")

        if self.stats['errors']:
            print("\nErreurs rencontrées:")
            for err in self.stats['errors'][:10]:
                print(f"  - {err}")
            if len(self.stats['errors']) > 10:
                print(f"  ... et {len(self.stats['errors']) - 10} autres")

        print("=" * 50)


def main():
    parser = argparse.ArgumentParser(
        description="Migration unified_contacts → companies + contacts"
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Affiche les actions sans les exécuter'
    )
    parser.add_argument(
        '--no-backup',
        action='store_true',
        help='Ne pas créer de backup (non recommandé)'
    )
    parser.add_argument(
        '--db-path',
        type=str,
        default=str(DB_PATH),
        help=f'Chemin vers la base de données (défaut: {DB_PATH})'
    )

    args = parser.parse_args()

    # Vérifier que la base existe
    if not Path(args.db_path).exists():
        logger.error(f"Base de données non trouvée: {args.db_path}")
        return 1

    # Exécuter la migration
    migration = MigrationScript(args.db_path, dry_run=args.dry_run)
    stats = migration.run(create_backup=not args.no_backup)

    # Code retour
    if stats['errors']:
        return 1
    return 0


if __name__ == "__main__":
    exit(main())
