"""
Module de tracking des leads pour éviter les doublons.
Utilise SQLite pour stocker l'historique des entreprises extraites.
"""
import sqlite3
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional, Set
from pathlib import Path

logger = logging.getLogger(__name__)


class LeadTracker:
    """
    Tracker de leads avec base de données SQLite.
    Permet de détecter et filtrer les entreprises déjà extraites.
    """

    def __init__(self, db_path: str = "data/leads_history.db"):
        """
        Initialise le tracker.

        Args:
            db_path: Chemin vers la base de données SQLite
        """
        self.db_path = db_path

        # Créer le dossier si nécessaire
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

        # Initialiser la base de données
        self._init_db()

    def _init_db(self):
        """Crée la table si elle n'existe pas."""
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
                    source TEXT DEFAULT 'SIRENE',
                    UNIQUE(siren)
                )
            """)

            # Index pour les recherches rapides
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_siren
                ON leads_history(siren)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_date
                ON leads_history(date_extraction)
            """)

            conn.commit()

        logger.info(f"Base de données initialisée : {self.db_path}")

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

    def filter_duplicates(self, companies: List[Dict[str, Any]]) -> tuple[List[Dict[str, Any]], int]:
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
        source: str = "SIRENE"
    ) -> int:
        """
        Ajoute des leads à l'historique.

        Args:
            companies: Liste d'entreprises à ajouter
            campagne_id: ID de la campagne d'extraction (optionnel)
            source: Source des données (SIRENE, PAPPERS, etc.)

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
                        (siren, denomination, code_ape, ville, date_extraction, campagne_id, source)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (
                        siren,
                        company.get('denomination', ''),
                        company.get('code_ape', ''),
                        company.get('ville', ''),
                        datetime.now(),
                        campagne_id,
                        source
                    ))

                    if cursor.rowcount > 0:
                        added += 1

                except sqlite3.IntegrityError:
                    # Doublon - déjà dans la base
                    pass

            conn.commit()

        logger.info(f"Ajouté {added} nouveaux leads à l'historique (campagne: {campagne_id})")
        return added

    def get_history(
        self,
        limit: int = 100,
        offset: int = 0,
        campagne_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Récupère l'historique des leads.

        Args:
            limit: Nombre max de résultats
            offset: Offset pour la pagination
            campagne_id: Filtrer par campagne (optionnel)

        Returns:
            Liste de leads avec leurs métadonnées
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            if campagne_id:
                cursor.execute("""
                    SELECT * FROM leads_history
                    WHERE campagne_id = ?
                    ORDER BY date_extraction DESC
                    LIMIT ? OFFSET ?
                """, (campagne_id, limit, offset))
            else:
                cursor.execute("""
                    SELECT * FROM leads_history
                    ORDER BY date_extraction DESC
                    LIMIT ? OFFSET ?
                """, (limit, offset))

            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    def get_stats(self) -> Dict[str, Any]:
        """
        Récupère des statistiques sur l'historique.

        Returns:
            Dict avec statistiques (total, par campagne, etc.)
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
                'campagnes_recentes': campagnes
            }

    def clear_history(self, older_than_days: Optional[int] = None) -> int:
        """
        Supprime l'historique (avec confirmation).

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
