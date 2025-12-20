"""
Synchronisation vers Google Sheets.
"""

import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from dataclasses import dataclass
from typing import Dict, List, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class SheetsSyncError(Exception):
    """Erreur spécifique à la sync Google Sheets."""
    pass


@dataclass
class SyncResult:
    """Résultat d'une synchronisation."""
    success: bool
    timestamp: str
    sheets_updated: List[str]
    total_rows: int
    error: Optional[str] = None


class GoogleSheetsSync:
    """Synchronisation Pipeline → Google Sheets."""

    SCOPES = [
        'https://www.googleapis.com/auth/spreadsheets',
        'https://www.googleapis.com/auth/drive'
    ]

    def __init__(self, credentials_path: str, spreadsheet_url: str):
        """
        Initialise la connexion Google Sheets.

        Args:
            credentials_path: Chemin vers le fichier JSON du Service Account
            spreadsheet_url: URL complète du Google Sheet
        """
        if not credentials_path:
            raise SheetsSyncError("Chemin credentials requis")
        if not spreadsheet_url:
            raise SheetsSyncError("URL du spreadsheet requise")

        try:
            creds = Credentials.from_service_account_file(
                credentials_path,
                scopes=self.SCOPES
            )
            self.gc = gspread.authorize(creds)
            self.spreadsheet = self.gc.open_by_url(spreadsheet_url)
            self.spreadsheet_url = spreadsheet_url
        except FileNotFoundError:
            raise SheetsSyncError(f"Fichier credentials introuvable: {credentials_path}")
        except gspread.exceptions.SpreadsheetNotFound:
            raise SheetsSyncError("Spreadsheet introuvable. Vérifiez l'URL et que le Sheet est partagé avec le Service Account.")
        except gspread.exceptions.APIError as e:
            raise SheetsSyncError(f"Erreur API Google: {e.response.text}")
        except ValueError as e:
            raise SheetsSyncError(f"Fichier credentials invalide: {e}")
        except Exception as e:
            error_type = type(e).__name__
            raise SheetsSyncError(f"{error_type}: {e}")

    def test_connection(self) -> Dict:
        """
        Teste la connexion au spreadsheet.

        Returns:
            Infos sur le spreadsheet
        """
        try:
            return {
                'title': self.spreadsheet.title,
                'url': self.spreadsheet_url,
                'sheets': [ws.title for ws in self.spreadsheet.worksheets()]
            }
        except Exception as e:
            raise SheetsSyncError(f"Erreur test connexion: {e}")

    def sync_pipeline(self, sheets_data: Dict[str, pd.DataFrame]) -> SyncResult:
        """
        Synchronise les données vers Google Sheets.

        Args:
            sheets_data: Dict avec {nom_onglet: DataFrame}

        Returns:
            SyncResult avec le statut de la sync
        """
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        sheets_updated = []
        total_rows = 0

        try:
            for sheet_name, df in sheets_data.items():
                self._write_to_sheet(df, sheet_name)
                sheets_updated.append(sheet_name)
                total_rows += len(df)
                logger.info(f"Onglet '{sheet_name}' mis à jour ({len(df)} lignes)")

            return SyncResult(
                success=True,
                timestamp=timestamp,
                sheets_updated=sheets_updated,
                total_rows=total_rows
            )

        except Exception as e:
            logger.error(f"Erreur sync: {e}")
            return SyncResult(
                success=False,
                timestamp=timestamp,
                sheets_updated=sheets_updated,
                total_rows=total_rows,
                error=str(e)
            )

    def _write_to_sheet(self, df: pd.DataFrame, sheet_name: str):
        """
        Écrit un DataFrame dans un onglet (mode replace).

        Args:
            df: DataFrame à écrire
            sheet_name: Nom de l'onglet
        """
        # Récupérer ou créer l'onglet
        try:
            worksheet = self.spreadsheet.worksheet(sheet_name)
        except gspread.WorksheetNotFound:
            worksheet = self.spreadsheet.add_worksheet(
                title=sheet_name,
                rows=max(1000, len(df) + 100),
                cols=max(30, len(df.columns) + 5)
            )
            logger.info(f"Onglet '{sheet_name}' créé")

        # Clear complet
        worksheet.clear()

        if df.empty:
            worksheet.update('A1', [['Aucune donnée']])
            return

        # Préparer les données
        # Convertir toutes les colonnes en string pour éviter les problèmes de sérialisation
        df_export = df.copy()
        for col in df_export.columns:
            df_export[col] = df_export[col].apply(self._serialize_value)

        # Header + données
        header = df_export.columns.tolist()
        values = df_export.values.tolist()
        data = [header] + values

        # Écrire en batch
        worksheet.update('A1', data, value_input_option='USER_ENTERED')

        # Formater l'en-tête (bold)
        try:
            worksheet.format('1:1', {'textFormat': {'bold': True}})
        except Exception:
            pass  # Ignorer les erreurs de formatage

    def _serialize_value(self, value) -> str:
        """
        Convertit une valeur pour Google Sheets.

        Args:
            value: Valeur à convertir

        Returns:
            Valeur sérialisée
        """
        if pd.isna(value) or value is None:
            return ''
        if isinstance(value, bool):
            return 'Oui' if value else 'Non'
        if isinstance(value, (int, float)):
            return value  # Garder comme nombre
        if isinstance(value, datetime):
            return value.strftime('%Y-%m-%d %H:%M:%S')
        return str(value)

    def clear_all_sheets(self):
        """Vide tous les onglets (utile pour reset)."""
        for worksheet in self.spreadsheet.worksheets():
            worksheet.clear()
        logger.info("Tous les onglets vidés")

    def read_sheet(self, sheet_name: str) -> Optional[pd.DataFrame]:
        """
        Lit les données d'un onglet existant.

        Args:
            sheet_name: Nom de l'onglet

        Returns:
            DataFrame avec les données ou None si l'onglet n'existe pas
        """
        try:
            worksheet = self.spreadsheet.worksheet(sheet_name)
            data = worksheet.get_all_values()
            if not data or len(data) < 2:
                return None
            # Première ligne = header
            df = pd.DataFrame(data[1:], columns=data[0])
            return df
        except gspread.WorksheetNotFound:
            return None
        except Exception as e:
            logger.warning(f"Erreur lecture onglet '{sheet_name}': {e}")
            return None

    def detect_changes(self, new_df: pd.DataFrame, existing_df: pd.DataFrame) -> List[Dict]:
        """
        Détecte les changements entre nouvelles données et données existantes.

        Args:
            new_df: Nouvelles données
            existing_df: Données existantes du sheet

        Returns:
            Liste des changements détectés
        """
        changes = []
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # Créer un dict des données existantes par Id
        existing_by_id = {}
        if existing_df is not None and not existing_df.empty and 'Id' in existing_df.columns:
            for _, row in existing_df.iterrows():
                existing_by_id[str(row['Id'])] = row.to_dict()

        # Comparer chaque nouvelle ligne
        for _, new_row in new_df.iterrows():
            task_id = str(new_row['Id'])
            task_name = new_row.get('Name', '')

            if task_id in existing_by_id:
                old_row = existing_by_id[task_id]
                # Comparer les champs (sauf Modified qui change toujours)
                fields_to_compare = ['Name', 'Budget', 'Status', 'Source', 'DocSuivi', 'Proba']
                changed_fields = []

                for field in fields_to_compare:
                    old_val = str(old_row.get(field, '') or '')
                    new_val = str(new_row.get(field, '') or '')
                    if old_val != new_val:
                        changed_fields.append({
                            'field': field,
                            'old': old_val,
                            'new': new_val
                        })

                if changed_fields:
                    changes.append({
                        'timestamp': timestamp,
                        'id': task_id,
                        'name': task_name,
                        'action': 'modified',
                        'changes': changed_fields
                    })
            else:
                # Nouvelle entrée
                changes.append({
                    'timestamp': timestamp,
                    'id': task_id,
                    'name': task_name,
                    'action': 'added',
                    'changes': []
                })

        # Vérifier les suppressions
        new_ids = set(str(row['Id']) for _, row in new_df.iterrows())
        for old_id, old_row in existing_by_id.items():
            if old_id not in new_ids:
                changes.append({
                    'timestamp': timestamp,
                    'id': old_id,
                    'name': old_row.get('Name', ''),
                    'action': 'removed',
                    'changes': []
                })

        return changes

    def log_changes(self, changes: List[Dict]):
        """
        Écrit les changements dans l'onglet Log.

        Args:
            changes: Liste des changements à logger
        """
        if not changes:
            return

        log_sheet_name = 'Log'

        # Récupérer ou créer l'onglet Log
        try:
            worksheet = self.spreadsheet.worksheet(log_sheet_name)
        except gspread.WorksheetNotFound:
            worksheet = self.spreadsheet.add_worksheet(
                title=log_sheet_name,
                rows=1000,
                cols=10
            )
            # Ajouter header
            header = ['Timestamp', 'Action', 'Id', 'Name', 'Field', 'Old Value', 'New Value']
            worksheet.update('A1', [header], value_input_option='USER_ENTERED')
            worksheet.format('1:1', {'textFormat': {'bold': True}})
            logger.info(f"Onglet '{log_sheet_name}' créé")

        # Préparer les lignes de log
        log_rows = []
        for change in changes:
            if change['action'] == 'modified':
                for field_change in change['changes']:
                    log_rows.append([
                        change['timestamp'],
                        'Modifié',
                        change['id'],
                        change['name'],
                        field_change['field'],
                        field_change['old'],
                        field_change['new']
                    ])
            elif change['action'] == 'added':
                log_rows.append([
                    change['timestamp'],
                    'Ajouté',
                    change['id'],
                    change['name'],
                    '',
                    '',
                    ''
                ])
            elif change['action'] == 'removed':
                log_rows.append([
                    change['timestamp'],
                    'Supprimé',
                    change['id'],
                    change['name'],
                    '',
                    '',
                    ''
                ])

        if log_rows:
            # Trouver la première ligne vide
            existing_data = worksheet.get_all_values()
            next_row = len(existing_data) + 1

            # Ajouter les nouvelles lignes
            cell_range = f'A{next_row}'
            worksheet.update(cell_range, log_rows, value_input_option='USER_ENTERED')
            logger.info(f"{len(log_rows)} entrées ajoutées au log")

    def sync_with_logging(self, df: pd.DataFrame, sheet_name: str = 'Pipeline') -> SyncResult:
        """
        Synchronise avec détection des changements et logging.

        Args:
            df: DataFrame à synchroniser
            sheet_name: Nom de l'onglet principal

        Returns:
            SyncResult avec statut et nombre de changements
        """
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        try:
            # Lire données existantes
            existing_df = self.read_sheet(sheet_name)

            # Détecter les changements
            changes = self.detect_changes(df, existing_df)

            # Logger les changements
            if changes:
                self.log_changes(changes)
                logger.info(f"{len(changes)} changements détectés et loggés")

            # Mettre à jour l'onglet principal
            self._write_to_sheet(df, sheet_name)

            return SyncResult(
                success=True,
                timestamp=timestamp,
                sheets_updated=[sheet_name, 'Log'] if changes else [sheet_name],
                total_rows=len(df)
            )

        except Exception as e:
            logger.error(f"Erreur sync: {e}")
            return SyncResult(
                success=False,
                timestamp=timestamp,
                sheets_updated=[],
                total_rows=0,
                error=str(e)
            )
