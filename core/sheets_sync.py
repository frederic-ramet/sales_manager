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
