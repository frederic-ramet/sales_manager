"""
Module de tracking des leads pour éviter les doublons.
Utilise SQLite pour stocker l'historique des entreprises extraites.
"""

import sqlite3
import logging
import json
from datetime import datetime
from typing import List, Dict, Any, Optional, Set, Tuple
from pathlib import Path

logger = logging.getLogger(__name__)

# Chemin par défaut de la base de données
DEFAULT_DB_PATH = Path(__file__).parent.parent.parent / "data" / "leads.db"


class LeadTracker:
    """
    Tracker de leads avec base de données SQLite.
    Permet de détecter et filtrer les entreprises déjà extraites.

    Usage:
        tracker = LeadTracker()
        filtered, num_dups = tracker.filter_duplicates(companies)
        tracker.add_leads(filtered, campagne_id="2024-01")
    """

    def __init__(self, db_path: Optional[str] = None):
        """
        Initialise le tracker.

        Args:
            db_path: Chemin vers la base de données SQLite (optionnel)
        """
        self.db_path = db_path or str(DEFAULT_DB_PATH)

        # Créer le dossier si nécessaire
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

        # Initialiser la base de données
        self._init_db()

    def _init_db(self):
        """Crée la table si elle n'existe pas et applique les migrations."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Table principale des leads
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS leads_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    siren TEXT NOT NULL,
                    denomination TEXT,
                    code_ape TEXT,
                    ville TEXT,
                    date_extraction TIMESTAMP NOT NULL,
                    campagne_id TEXT,
                    source TEXT DEFAULT 'sirene',
                    UNIQUE(siren)
                )
            """)

            # Migration : ajouter nouvelles colonnes si absentes
            self._migrate_add_columns(cursor)

            # Index pour les recherches rapides
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_siren
                ON leads_history(siren)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_date
                ON leads_history(date_extraction)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_campagne
                ON leads_history(campagne_id)
            """)

            conn.commit()

        logger.info(f"Base de données initialisée: {self.db_path}")

    def _migrate_add_columns(self, cursor):
        """Ajoute les nouvelles colonnes si elles n'existent pas."""
        # Récupérer les colonnes existantes
        cursor.execute("PRAGMA table_info(leads_history)")
        existing_columns = {row[1] for row in cursor.fetchall()}

        # Colonnes à ajouter (nom, type, default)
        new_columns = [
            ("hubspot_id", "TEXT", None),
            ("email", "TEXT", None),
            ("telephone", "TEXT", None),
            ("dirigeant_nom", "TEXT", None),
            ("dirigeant_prenom", "TEXT", None),
            ("enriched_at", "TIMESTAMP", None),
            ("last_sync_hubspot", "TIMESTAMP", None),
            ("full_data", "TEXT", None),  # JSON blob pour tous les champs
        ]

        for col_name, col_type, default in new_columns:
            if col_name not in existing_columns:
                try:
                    if default is not None:
                        cursor.execute(f"ALTER TABLE leads_history ADD COLUMN {col_name} {col_type} DEFAULT '{default}'")
                    else:
                        cursor.execute(f"ALTER TABLE leads_history ADD COLUMN {col_name} {col_type}")
                    logger.info(f"Migration: ajouté colonne {col_name}")
                except sqlite3.OperationalError:
                    pass  # Colonne existe déjà

        # Index supplémentaires
        try:
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_hubspot_id ON leads_history(hubspot_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_source ON leads_history(source)")
        except sqlite3.OperationalError:
            pass

    def is_duplicate(self, siren: str) -> bool:
        """
        Vérifie si un SIREN a déjà été extrait.

        Args:
            siren: Numéro SIREN de l'entreprise

        Returns:
            True si le SIREN est déjà dans l'historique
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT COUNT(*) FROM leads_history WHERE siren = ?",
                (siren,)
            )
            count = cursor.fetchone()[0]
            return count > 0

    def get_duplicates(self, sirens: List[str]) -> Set[str]:
        """
        Trouve tous les SIREN déjà extraits dans une liste.

        Args:
            sirens: Liste de SIREN à vérifier

        Returns:
            Ensemble des SIREN déjà présents dans l'historique
        """
        if not sirens:
            return set()

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Requête IN avec paramètres
            placeholders = ','.join('?' * len(sirens))
            query = f"SELECT siren FROM leads_history WHERE siren IN ({placeholders})"

            cursor.execute(query, sirens)
            duplicates = {row[0] for row in cursor.fetchall()}

            return duplicates

    def filter_duplicates(self, companies: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], int]:
        """
        Filtre les entreprises déjà extraites.

        Args:
            companies: Liste d'entreprises à filtrer

        Returns:
            Tuple (entreprises filtrées, nombre de doublons)
        """
        if not companies:
            return [], 0

        # Extraire tous les SIREN
        sirens = [company.get('siren') for company in companies if company.get('siren')]

        # Trouver les doublons
        duplicates = self.get_duplicates(sirens)

        # Filtrer
        filtered = [
            company for company in companies
            if company.get('siren') not in duplicates
        ]

        num_duplicates = len(companies) - len(filtered)

        if num_duplicates > 0:
            logger.info(f"Filtrage de {num_duplicates} doublons sur {len(companies)} entreprises")

        return filtered, num_duplicates

    def add_leads(
        self,
        companies: List[Dict[str, Any]],
        campagne_id: Optional[str] = None,
        source: str = "sirene"
    ) -> int:
        """
        Ajoute des leads à l'historique.

        Args:
            companies: Liste d'entreprises à ajouter
            campagne_id: ID de la campagne d'extraction (optionnel)
            source: Source des données (sirene, hubspot, getsales)

        Returns:
            Nombre de leads ajoutés (hors doublons)
        """
        if not companies:
            return 0

        # Générer un ID de campagne si non fourni
        if not campagne_id:
            campagne_id = datetime.now().strftime("%Y%m%d_%H%M%S")

        added = 0
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            for company in companies:
                siren = company.get('siren')
                if not siren:
                    continue

                try:
                    cursor.execute("""
                        INSERT OR IGNORE INTO leads_history
                        (siren, denomination, code_ape, ville, date_extraction, campagne_id, source,
                         hubspot_id, email, telephone, dirigeant_nom, dirigeant_prenom, full_data)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        siren,
                        company.get('denomination', ''),
                        company.get('code_ape', ''),
                        company.get('ville', ''),
                        datetime.now(),
                        campagne_id,
                        source.lower(),
                        company.get('hubspot_id'),
                        company.get('email'),
                        company.get('telephone'),
                        company.get('dirigeant_nom'),
                        company.get('dirigeant_prenom'),
                        json.dumps(company, ensure_ascii=False, default=str)
                    ))

                    if cursor.rowcount > 0:
                        added += 1

                except sqlite3.IntegrityError:
                    # Doublon - déjà dans la base
                    pass

            conn.commit()

        logger.info(f"Ajouté {added} nouveaux leads à l'historique (campagne: {campagne_id})")
        return added

    def update_lead(self, siren: str, data: Dict[str, Any], mark_enriched: bool = False) -> bool:
        """
        Met à jour un lead existant.

        Args:
            siren: SIREN du lead à mettre à jour
            data: Données à mettre à jour
            mark_enriched: Si True, marque enriched_at à maintenant

        Returns:
            True si mis à jour, False sinon
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Construire la requête dynamiquement
            fields_to_update = []
            values = []

            field_mapping = {
                'denomination': 'denomination',
                'code_ape': 'code_ape',
                'ville': 'ville',
                'email': 'email',
                'telephone': 'telephone',
                'dirigeant_nom': 'dirigeant_nom',
                'dirigeant_prenom': 'dirigeant_prenom',
                'hubspot_id': 'hubspot_id',
            }

            for key, col in field_mapping.items():
                if key in data and data[key]:
                    fields_to_update.append(f"{col} = ?")
                    values.append(data[key])

            # Toujours mettre à jour full_data
            fields_to_update.append("full_data = ?")
            values.append(json.dumps(data, ensure_ascii=False, default=str))

            if mark_enriched:
                fields_to_update.append("enriched_at = ?")
                values.append(datetime.now())

            if not fields_to_update:
                return False

            values.append(siren)
            query = f"UPDATE leads_history SET {', '.join(fields_to_update)} WHERE siren = ?"

            cursor.execute(query, values)
            conn.commit()

            return cursor.rowcount > 0

    def get_leads_for_enrichment(self, limit: int = 50, source: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Récupère les leads non encore enrichis.

        Args:
            limit: Nombre max de résultats
            source: Filtrer par source (optionnel)

        Returns:
            Liste de leads à enrichir
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            if source:
                cursor.execute("""
                    SELECT * FROM leads_history
                    WHERE enriched_at IS NULL AND source = ?
                    ORDER BY date_extraction DESC
                    LIMIT ?
                """, (source.lower(), limit))
            else:
                cursor.execute("""
                    SELECT * FROM leads_history
                    WHERE enriched_at IS NULL
                    ORDER BY date_extraction DESC
                    LIMIT ?
                """, (limit,))

            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    def mark_synced_to_hubspot(self, siren: str, hubspot_id: str) -> bool:
        """
        Marque un lead comme synchronisé vers HubSpot.

        Args:
            siren: SIREN du lead
            hubspot_id: ID du contact/entreprise dans HubSpot

        Returns:
            True si mis à jour
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE leads_history
                SET hubspot_id = ?, last_sync_hubspot = ?
                WHERE siren = ?
            """, (hubspot_id, datetime.now(), siren))
            conn.commit()
            return cursor.rowcount > 0

    def get_history(
        self,
        limit: int = 100,
        offset: int = 0,
        campagne_id: Optional[str] = None,
        source: Optional[str] = None,
        search: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Récupère l'historique des leads.

        Args:
            limit: Nombre max de résultats
            offset: Offset pour la pagination
            campagne_id: Filtrer par campagne (optionnel)
            source: Filtrer par source (optionnel)
            search: Recherche texte sur siren/denomination/email (optionnel)

        Returns:
            Liste de leads avec leurs métadonnées
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Construire la requête avec filtres
            conditions = []
            params = []

            if campagne_id:
                conditions.append("campagne_id = ?")
                params.append(campagne_id)

            if source:
                conditions.append("source = ?")
                params.append(source.lower())

            if search:
                conditions.append("(siren LIKE ? OR denomination LIKE ? OR email LIKE ?)")
                search_term = f"%{search}%"
                params.extend([search_term, search_term, search_term])

            where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

            query = f"""
                SELECT * FROM leads_history
                {where_clause}
                ORDER BY date_extraction DESC
                LIMIT ? OFFSET ?
            """
            params.extend([limit, offset])

            cursor.execute(query, params)
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    def get_stats(self) -> Dict[str, Any]:
        """
        Récupère des statistiques sur l'historique.

        Returns:
            Dict avec statistiques (total, par campagne, par source, etc.)
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Total de leads
            cursor.execute("SELECT COUNT(*) FROM leads_history")
            total = cursor.fetchone()[0]

            # Nombre de campagnes
            cursor.execute("SELECT COUNT(DISTINCT campagne_id) FROM leads_history")
            num_campagnes = cursor.fetchone()[0]

            # Lead le plus récent
            cursor.execute("""
                SELECT date_extraction
                FROM leads_history
                ORDER BY date_extraction DESC
                LIMIT 1
            """)
            row = cursor.fetchone()
            dernier_lead = row[0] if row else None

            # Par source
            cursor.execute("""
                SELECT COALESCE(source, 'sirene') as source, COUNT(*) as count
                FROM leads_history
                GROUP BY source
            """)
            by_source = {row[0]: row[1] for row in cursor.fetchall()}

            # Leads enrichis
            cursor.execute("SELECT COUNT(*) FROM leads_history WHERE enriched_at IS NOT NULL")
            enriched_count = cursor.fetchone()[0]

            # Leads synchro HubSpot
            cursor.execute("SELECT COUNT(*) FROM leads_history WHERE hubspot_id IS NOT NULL")
            hubspot_synced = cursor.fetchone()[0]

            # Par campagne
            cursor.execute("""
                SELECT campagne_id, COUNT(*) as count, MIN(date_extraction) as date
                FROM leads_history
                GROUP BY campagne_id
                ORDER BY date DESC
                LIMIT 10
            """)
            campagnes = [
                {
                    'campagne_id': row[0],
                    'count': row[1],
                    'date': row[2]
                }
                for row in cursor.fetchall()
            ]

            return {
                'total_leads': total,
                'num_campagnes': num_campagnes,
                'dernier_lead': dernier_lead,
                'campagnes_recentes': campagnes,
                'by_source': by_source,
                'enriched_count': enriched_count,
                'hubspot_synced': hubspot_synced
            }

    def get_total_count(self) -> int:
        """
        Retourne le nombre total de leads dans l'historique.

        Returns:
            Nombre total de SIREN uniques
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM leads_history")
            return cursor.fetchone()[0]

    def clear_history(self, older_than_days: Optional[int] = None) -> int:
        """
        Supprime l'historique.

        Args:
            older_than_days: Supprimer uniquement les leads plus vieux que N jours (optionnel)

        Returns:
            Nombre de leads supprimés
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            if older_than_days:
                cursor.execute("""
                    DELETE FROM leads_history
                    WHERE date_extraction < datetime('now', '-' || ? || ' days')
                """, (older_than_days,))
            else:
                cursor.execute("DELETE FROM leads_history")

            deleted = cursor.rowcount
            conn.commit()

        logger.warning(f"Supprimé {deleted} leads de l'historique")
        return deleted

    def delete_campagne(self, campagne_id: str) -> int:
        """
        Supprime tous les leads d'une campagne.

        Args:
            campagne_id: ID de la campagne à supprimer

        Returns:
            Nombre de leads supprimés
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM leads_history WHERE campagne_id = ?",
                (campagne_id,)
            )
            deleted = cursor.rowcount
            conn.commit()

        logger.info(f"Supprimé {deleted} leads de la campagne {campagne_id}")
        return deleted
