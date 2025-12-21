#!/usr/bin/env python3
"""
Script de vérification post-migration.

Vérifie l'intégrité des données après la migration:
- Nombre total de contacts préservé
- Pas de SIREN dupliqués dans companies
- Intégrité des foreign keys
- Unicité email/linkedin préservée
- Stats companies correctes

Usage:
    python scripts/verify_migration.py [--db-path PATH]
"""

import sqlite3
import argparse
import logging
from pathlib import Path
from typing import Dict, List, Tuple

# Configuration logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Chemins
BASE_DIR = Path(__file__).parent.parent
DB_PATH = BASE_DIR / "data" / "leads.db"


class MigrationVerifier:
    """Vérifie l'intégrité post-migration."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self.checks = []
        self.errors = []
        self.warnings = []

    def run(self) -> bool:
        """
        Exécute toutes les vérifications.

        Returns:
            True si toutes les vérifications passent
        """
        logger.info("=== Vérification post-migration ===")

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row

            # Vérifier que les tables existent
            if not self._check_tables_exist(conn):
                return False

            # 1. Vérifier nombre total contacts
            self._check_contact_count(conn)

            # 2. Vérifier unicité SIREN
            self._check_siren_uniqueness(conn)

            # 3. Vérifier intégrité FK
            self._check_foreign_keys(conn)

            # 4. Vérifier unicité email/linkedin
            self._check_email_uniqueness(conn)
            self._check_linkedin_uniqueness(conn)

            # 5. Vérifier stats companies
            self._check_company_stats(conn)

            # 6. Vérifier données critiques non perdues
            self._check_critical_data(conn)

            # 7. Vérifier vue legacy
            self._check_legacy_view(conn)

        # Afficher résultats
        self._print_results()

        return len(self.errors) == 0

    def _check_tables_exist(self, conn: sqlite3.Connection) -> bool:
        """Vérifie que les tables requises existent."""
        cursor = conn.cursor()

        required_tables = ['companies', 'contacts']
        for table in required_tables:
            cursor.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name=?
            """, (table,))
            if not cursor.fetchone():
                self.errors.append(f"Table '{table}' non trouvée!")
                return False

        self.checks.append("✅ Tables companies et contacts existent")
        return True

    def _check_contact_count(self, conn: sqlite3.Connection):
        """Vérifie que le nombre de contacts est préservé."""
        cursor = conn.cursor()

        # Compter dans contacts
        cursor.execute("SELECT COUNT(*) FROM contacts WHERE status = 'active'")
        contacts_count = cursor.fetchone()[0]

        # Compter dans backup si existe
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='unified_contacts_backup'
        """)
        if cursor.fetchone():
            cursor.execute("SELECT COUNT(*) FROM unified_contacts_backup WHERE status = 'active'")
            backup_count = cursor.fetchone()[0]

            if contacts_count == backup_count:
                self.checks.append(f"✅ Nombre de contacts préservé: {contacts_count}")
            else:
                diff = backup_count - contacts_count
                if diff > 0:
                    self.warnings.append(
                        f"⚠️ {diff} contacts manquants (backup: {backup_count}, new: {contacts_count})"
                    )
                else:
                    self.warnings.append(
                        f"⚠️ {-diff} contacts en plus (backup: {backup_count}, new: {contacts_count})"
                    )
        else:
            self.checks.append(f"ℹ️ Contacts dans nouvelle table: {contacts_count} (pas de backup)")

    def _check_siren_uniqueness(self, conn: sqlite3.Connection):
        """Vérifie qu'il n'y a pas de SIREN dupliqués."""
        cursor = conn.cursor()

        cursor.execute("""
            SELECT siren, COUNT(*) as cnt
            FROM companies
            WHERE siren IS NOT NULL AND siren != ''
            GROUP BY siren
            HAVING cnt > 1
        """)
        duplicates = cursor.fetchall()

        if duplicates:
            for row in duplicates:
                self.errors.append(f"❌ SIREN dupliqué: {row['siren']} ({row['cnt']} fois)")
        else:
            cursor.execute("""
                SELECT COUNT(DISTINCT siren) FROM companies
                WHERE siren IS NOT NULL AND siren != ''
            """)
            unique_count = cursor.fetchone()[0]
            self.checks.append(f"✅ Unicité SIREN OK ({unique_count} SIREN uniques)")

    def _check_foreign_keys(self, conn: sqlite3.Connection):
        """Vérifie l'intégrité des foreign keys."""
        cursor = conn.cursor()

        # Contacts avec company_id invalide
        cursor.execute("""
            SELECT COUNT(*) FROM contacts
            WHERE company_id IS NOT NULL
              AND company_id NOT IN (SELECT id FROM companies)
        """)
        invalid_fk = cursor.fetchone()[0]

        if invalid_fk > 0:
            self.errors.append(f"❌ {invalid_fk} contacts avec company_id invalide")
        else:
            cursor.execute("""
                SELECT COUNT(*) FROM contacts WHERE company_id IS NOT NULL
            """)
            linked = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM contacts")
            total = cursor.fetchone()[0]
            self.checks.append(f"✅ FK intégrité OK ({linked}/{total} contacts liés à une entreprise)")

    def _check_email_uniqueness(self, conn: sqlite3.Connection):
        """Vérifie l'unicité des emails."""
        cursor = conn.cursor()

        cursor.execute("""
            SELECT email, COUNT(*) as cnt
            FROM contacts
            WHERE email IS NOT NULL AND email != ''
            GROUP BY LOWER(email)
            HAVING cnt > 1
        """)
        duplicates = cursor.fetchall()

        if duplicates:
            for row in duplicates[:5]:
                self.warnings.append(f"⚠️ Email dupliqué: {row['email']} ({row['cnt']} fois)")
            if len(duplicates) > 5:
                self.warnings.append(f"  ... et {len(duplicates) - 5} autres emails dupliqués")
        else:
            cursor.execute("""
                SELECT COUNT(DISTINCT LOWER(email)) FROM contacts
                WHERE email IS NOT NULL AND email != ''
            """)
            unique_count = cursor.fetchone()[0]
            self.checks.append(f"✅ Unicité email OK ({unique_count} emails uniques)")

    def _check_linkedin_uniqueness(self, conn: sqlite3.Connection):
        """Vérifie l'unicité des URLs LinkedIn."""
        cursor = conn.cursor()

        cursor.execute("""
            SELECT linkedin_url, COUNT(*) as cnt
            FROM contacts
            WHERE linkedin_url IS NOT NULL AND linkedin_url != ''
            GROUP BY LOWER(linkedin_url)
            HAVING cnt > 1
        """)
        duplicates = cursor.fetchall()

        if duplicates:
            for row in duplicates[:5]:
                self.warnings.append(f"⚠️ LinkedIn dupliqué: {row['linkedin_url'][:50]}... ({row['cnt']} fois)")
            if len(duplicates) > 5:
                self.warnings.append(f"  ... et {len(duplicates) - 5} autres LinkedIn dupliqués")
        else:
            cursor.execute("""
                SELECT COUNT(DISTINCT LOWER(linkedin_url)) FROM contacts
                WHERE linkedin_url IS NOT NULL AND linkedin_url != ''
            """)
            unique_count = cursor.fetchone()[0]
            self.checks.append(f"✅ Unicité LinkedIn OK ({unique_count} URLs uniques)")

    def _check_company_stats(self, conn: sqlite3.Connection):
        """Vérifie que les stats companies sont correctes."""
        cursor = conn.cursor()

        # Vérifier total_contacts
        cursor.execute("""
            SELECT c.id, c.company_name, c.total_contacts,
                   (SELECT COUNT(*) FROM contacts WHERE company_id = c.id) as real_count
            FROM companies c
            WHERE c.total_contacts != (SELECT COUNT(*) FROM contacts WHERE company_id = c.id)
            LIMIT 10
        """)
        mismatches = cursor.fetchall()

        if mismatches:
            for row in mismatches[:3]:
                self.warnings.append(
                    f"⚠️ Stats incorrectes pour {row['company_name']}: "
                    f"total_contacts={row['total_contacts']}, réel={row['real_count']}"
                )
            if len(mismatches) > 3:
                self.warnings.append(f"  ... et {len(mismatches) - 3} autres entreprises")
        else:
            self.checks.append("✅ Stats companies OK (total_contacts correct)")

    def _check_critical_data(self, conn: sqlite3.Connection):
        """Vérifie que les données critiques n'ont pas été perdues."""
        cursor = conn.cursor()

        # Vérifier qu'on a des emails
        cursor.execute("""
            SELECT COUNT(*) FROM contacts
            WHERE email IS NOT NULL AND email != ''
        """)
        email_count = cursor.fetchone()[0]

        # Vérifier qu'on a des entreprises avec SIREN
        cursor.execute("""
            SELECT COUNT(*) FROM companies
            WHERE siren IS NOT NULL AND siren != ''
        """)
        siren_count = cursor.fetchone()[0]

        # Vérifier GetSales UUIDs
        cursor.execute("""
            SELECT COUNT(*) FROM contacts
            WHERE getsales_uuid IS NOT NULL AND getsales_uuid != ''
        """)
        getsales_count = cursor.fetchone()[0]

        # Vérifier HubSpot IDs
        cursor.execute("""
            SELECT COUNT(*) FROM contacts
            WHERE hubspot_contact_id IS NOT NULL AND hubspot_contact_id != ''
        """)
        hubspot_count = cursor.fetchone()[0]

        self.checks.append(f"ℹ️ Données critiques: {email_count} emails, {siren_count} SIREN, "
                          f"{getsales_count} GetSales, {hubspot_count} HubSpot")

    def _check_legacy_view(self, conn: sqlite3.Connection):
        """Vérifie que la vue legacy fonctionne."""
        cursor = conn.cursor()

        # Vérifier que la vue existe
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='view' AND name IN ('unified_contacts_legacy', 'unified_contacts')
        """)
        views = cursor.fetchall()

        if not views:
            self.warnings.append("⚠️ Vue de compatibilité legacy non trouvée")
            return

        view_name = views[0]['name']

        try:
            cursor.execute(f"SELECT COUNT(*) FROM {view_name}")
            count = cursor.fetchone()[0]
            self.checks.append(f"✅ Vue '{view_name}' fonctionne ({count} lignes)")
        except Exception as e:
            self.errors.append(f"❌ Vue '{view_name}' erreur: {e}")

    def _print_results(self):
        """Affiche les résultats des vérifications."""
        print("\n" + "=" * 60)
        print("RÉSULTATS DE LA VÉRIFICATION")
        print("=" * 60)

        print("\n📋 Vérifications réussies:")
        for check in self.checks:
            print(f"  {check}")

        if self.warnings:
            print("\n⚠️ Avertissements:")
            for warn in self.warnings:
                print(f"  {warn}")

        if self.errors:
            print("\n❌ Erreurs:")
            for err in self.errors:
                print(f"  {err}")

        print("\n" + "=" * 60)
        if self.errors:
            print("RÉSULTAT: ÉCHEC - Des erreurs ont été détectées")
        elif self.warnings:
            print("RÉSULTAT: OK AVEC AVERTISSEMENTS")
        else:
            print("RÉSULTAT: SUCCÈS - Toutes les vérifications passées")
        print("=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description="Vérification post-migration"
    )
    parser.add_argument(
        '--db-path',
        type=str,
        default=str(DB_PATH),
        help=f'Chemin vers la base de données (défaut: {DB_PATH})'
    )

    args = parser.parse_args()

    if not Path(args.db_path).exists():
        logger.error(f"Base de données non trouvée: {args.db_path}")
        return 1

    verifier = MigrationVerifier(args.db_path)
    success = verifier.run()

    return 0 if success else 1


if __name__ == "__main__":
    exit(main())
