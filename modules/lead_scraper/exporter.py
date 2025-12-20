"""
Module d'export des données vers CSV, Google Sheets et HubSpot.
Gère le formatage et l'envoi des données enrichies.
"""
import csv
import logging
import os
from datetime import datetime
from typing import List, Dict, Any, Optional, TYPE_CHECKING
from pathlib import Path

import gspread
from google.oauth2.service_account import Credentials

if TYPE_CHECKING:
    from .hubspot_client import HubSpotClient

logger = logging.getLogger(__name__)

# Chemin par défaut pour les exports
DEFAULT_EXPORTS_DIR = Path(__file__).parent.parent.parent / "exports"
DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"


class Exporter:
    """
    Gestionnaire d'export des données vers CSV et Google Sheets.

    Usage:
        exporter = Exporter(credentials_path='credentials/service-account.json')
        exporter.to_csv(data, 'leads_2024')
        exporter.to_google_sheet(data, 'SHEET_ID')
    """

    # Colonnes pour l'export
    COLUMNS = [
        "SIREN",
        "Dénomination",
        "Code APE",
        "Activité",
        "Adresse",
        "CP",
        "Ville",
        "Dirigeant",
        "Fonction",
        "Email",
        "Téléphone",
        "Site web",
        "CA",
        "Effectif",
        "Date extraction"
    ]

    def __init__(
        self,
        credentials_path: Optional[str] = None,
        hubspot_client: Optional["HubSpotClient"] = None,
        exports_dir: Optional[str] = None
    ):
        """
        Initialise l'exporter.

        Args:
            credentials_path: Chemin vers le fichier JSON des credentials GCP
            hubspot_client: Client HubSpot pour export CRM (optionnel)
            exports_dir: Dossier pour les exports CSV (optionnel)
        """
        self.credentials_path = credentials_path or os.getenv(
            'GOOGLE_CREDENTIALS_PATH',
            'credentials/service-account.json'
        )
        self.gspread_client: Optional[gspread.Client] = None
        self.hubspot_client = hubspot_client
        self.exports_dir = exports_dir or str(DEFAULT_EXPORTS_DIR)

        # Créer le dossier d'exports s'il n'existe pas
        os.makedirs(self.exports_dir, exist_ok=True)

    def _get_gspread_client(self) -> gspread.Client:
        """
        Initialise et retourne le client Google Sheets.

        Returns:
            Client gspread authentifié

        Raises:
            ValueError: Si les credentials ne sont pas configurés
        """
        if self.gspread_client:
            return self.gspread_client

        if not self.credentials_path:
            raise ValueError(
                "Chemin des credentials Google non défini. "
                "Passez credentials_path au constructeur."
            )

        if not os.path.exists(self.credentials_path):
            raise FileNotFoundError(
                f"Fichier credentials introuvable: {self.credentials_path}"
            )

        try:
            # Scopes nécessaires pour Google Sheets
            scopes = [
                'https://www.googleapis.com/auth/spreadsheets',
                'https://www.googleapis.com/auth/drive'
            ]

            logger.info(f"Chargement des credentials depuis: {self.credentials_path}")
            credentials = Credentials.from_service_account_file(
                self.credentials_path,
                scopes=scopes
            )

            # Récupérer l'email du service account pour le log
            service_account_email = credentials.service_account_email
            logger.info(f"Service account: {service_account_email}")

            self.gspread_client = gspread.authorize(credentials)
            logger.info("Client Google Sheets initialisé avec succès")

            return self.gspread_client

        except FileNotFoundError as e:
            error_msg = f"Fichier credentials introuvable: {self.credentials_path}"
            logger.error(error_msg)
            raise ValueError(error_msg) from e
        except ValueError as e:
            error_msg = f"Fichier credentials invalide (JSON malformé?): {e}"
            logger.error(error_msg)
            raise ValueError(error_msg) from e
        except Exception as e:
            error_msg = f"Erreur lors de l'initialisation du client Google Sheets: {type(e).__name__}: {e}"
            logger.error(error_msg)
            raise ValueError(error_msg) from e

    def _format_row(self, company: Dict[str, Any]) -> List[str]:
        """
        Formate une entreprise en ligne pour l'export.

        Args:
            company: Dict avec les données de l'entreprise

        Returns:
            Liste de valeurs correspondant aux colonnes
        """
        # Formater le dirigeant (nom + prénom)
        dirigeant_parts = []
        if company.get("dirigeant_prenom"):
            dirigeant_parts.append(company["dirigeant_prenom"])
        if company.get("dirigeant_nom"):
            dirigeant_parts.append(company["dirigeant_nom"])
        dirigeant = " ".join(dirigeant_parts) if dirigeant_parts else ""

        return [
            company.get("siren", ""),
            company.get("denomination", ""),
            company.get("code_ape", ""),
            company.get("libelle_ape", ""),
            company.get("adresse", ""),
            company.get("code_postal", ""),
            company.get("ville", ""),
            dirigeant,
            company.get("dirigeant_fonction", ""),
            company.get("email", ""),
            company.get("telephone", ""),
            company.get("site_web", ""),
            company.get("chiffre_affaires", ""),
            company.get("effectif", ""),
            datetime.now().strftime(DATETIME_FORMAT)
        ]

    def to_csv(self, data: List[Dict[str, Any]], filename: str) -> str:
        """
        Export les données vers un fichier CSV.

        Args:
            data: Liste d'entreprises enrichies
            filename: Nom du fichier (sans extension)

        Returns:
            Chemin complet du fichier créé
        """
        if not data:
            logger.warning("Aucune donnée à exporter en CSV")
            return ""

        # Générer le nom de fichier complet
        if not filename.endswith(".csv"):
            filename = f"{filename}.csv"

        filepath = os.path.join(self.exports_dir, filename)

        try:
            with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile, delimiter=';')

                # Header
                writer.writerow(self.COLUMNS)

                # Données
                for company in data:
                    row = self._format_row(company)
                    writer.writerow(row)

            logger.info(f"Export CSV réussi: {filepath} ({len(data)} lignes)")
            return filepath

        except Exception as e:
            logger.error(f"Erreur lors de l'export CSV: {e}")
            raise

    def to_google_sheet(
        self,
        data: List[Dict[str, Any]],
        sheet_id: str,
        worksheet_name: Optional[str] = None
    ) -> str:
        """
        Export les données vers Google Sheets.

        Args:
            data: Liste d'entreprises enrichies
            sheet_id: ID du Google Sheet cible
            worksheet_name: Nom de la feuille (généré automatiquement si None)

        Returns:
            URL du Google Sheet
        """
        if not data:
            logger.warning("Aucune donnée à exporter vers Google Sheets")
            return ""

        # Nom de la feuille par défaut
        if not worksheet_name:
            worksheet_name = f"Leads_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        try:
            # Initialiser le client
            logger.info("Initialisation du client Google Sheets...")
            client = self._get_gspread_client()
            logger.info("Client Google Sheets prêt")

            # Ouvrir le spreadsheet
            logger.info(f"Ouverture du spreadsheet avec ID: {sheet_id}")
            spreadsheet = client.open_by_key(sheet_id)
            logger.info(f"Spreadsheet ouvert avec succès: {spreadsheet.title}")

            # Créer ou récupérer la worksheet
            try:
                worksheet = spreadsheet.worksheet(worksheet_name)
                logger.info(f"Worksheet existante trouvée: {worksheet_name}")
                # Vider la worksheet existante
                worksheet.clear()
            except gspread.WorksheetNotFound:
                worksheet = spreadsheet.add_worksheet(
                    title=worksheet_name,
                    rows=len(data) + 1,
                    cols=len(self.COLUMNS)
                )
                logger.info(f"Nouvelle worksheet créée: {worksheet_name}")

            # Préparer les données
            rows = [self.COLUMNS]  # Header
            for company in data:
                rows.append(self._format_row(company))

            # Écrire toutes les données en une seule fois (plus performant)
            worksheet.update(
                range_name='A1',
                values=rows,
                value_input_option='USER_ENTERED'
            )

            # Formater le header (optionnel mais joli)
            worksheet.format('A1:O1', {
                'textFormat': {'bold': True},
                'backgroundColor': {'red': 0.2, 'green': 0.2, 'blue': 0.2},
            })

            # Figer la première ligne
            worksheet.freeze(rows=1)

            # URL du spreadsheet
            sheet_url = spreadsheet.url

            logger.info(
                f"Export Google Sheets réussi: {worksheet_name} "
                f"({len(data)} lignes)"
            )

            return sheet_url

        except gspread.exceptions.APIError as e:
            error_msg = f"Erreur API Google Sheets: {e}"
            if "PERMISSION_DENIED" in str(e):
                error_msg += " - Le service account n'a pas accès au Sheet"
            elif "NOT_FOUND" in str(e):
                error_msg += " - Sheet introuvable avec cet ID"
            logger.error(error_msg)
            raise Exception(error_msg) from e
        except gspread.exceptions.SpreadsheetNotFound:
            error_msg = f"Spreadsheet introuvable avec l'ID: {sheet_id}"
            logger.error(error_msg)
            raise Exception(error_msg)
        except Exception as e:
            error_msg = f"Erreur lors de l'export Google Sheets: {type(e).__name__}: {e}"
            logger.error(error_msg)
            raise Exception(error_msg) from e

    def to_hubspot(self, data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Export les données vers HubSpot.

        Args:
            data: Liste d'entreprises enrichies

        Returns:
            Dict avec résultats (created, errors)
        """
        if not data:
            logger.warning("Aucune donnée à exporter vers HubSpot")
            return {"created": 0, "errors": []}

        if not self.hubspot_client:
            raise ValueError("Client HubSpot non configuré")

        try:
            logger.info(f"Export de {len(data)} contacts vers HubSpot...")

            # Push vers HubSpot
            result = self.hubspot_client.push_contacts(data)

            # Mettre à jour le miroir local
            if result["created"] > 0:
                self.hubspot_client.update_mirror_with_pushed(data)

            logger.info(
                f"Export HubSpot terminé: {result['created']} créés, "
                f"{len(result['errors'])} erreurs"
            )

            return result

        except Exception as e:
            logger.error(f"Erreur lors de l'export HubSpot: {e}")
            raise

    def export_all(
        self,
        data: List[Dict[str, Any]],
        csv_filename: str,
        sheet_id: Optional[str] = None,
        worksheet_name: Optional[str] = None,
        enable_hubspot: bool = False
    ) -> Dict[str, str]:
        """
        Export vers CSV, Google Sheets et HubSpot en une seule opération.

        Args:
            data: Liste d'entreprises enrichies
            csv_filename: Nom du fichier CSV
            sheet_id: ID du Google Sheet (optionnel)
            worksheet_name: Nom de la feuille (optionnel)
            enable_hubspot: Activer l'export vers HubSpot

        Returns:
            Dict avec 'csv_path', 'sheet_url', 'hubspot_created' (si applicable)
        """
        results = {}

        # Export CSV
        try:
            csv_path = self.to_csv(data, csv_filename)
            results['csv_path'] = csv_path
        except Exception as e:
            logger.error(f"Échec de l'export CSV: {e}")
            results['csv_error'] = str(e)

        # Export Google Sheets
        if sheet_id:
            try:
                sheet_url = self.to_google_sheet(data, sheet_id, worksheet_name)
                results['sheet_url'] = sheet_url
            except Exception as e:
                logger.error(f"Échec de l'export Google Sheets: {e}")
                results['sheet_error'] = str(e)

        # Export HubSpot
        if enable_hubspot and self.hubspot_client:
            try:
                hubspot_result = self.to_hubspot(data)
                results['hubspot_created'] = hubspot_result['created']
                if hubspot_result['errors']:
                    results['hubspot_errors'] = hubspot_result['errors']
            except Exception as e:
                logger.error(f"Échec de l'export HubSpot: {e}")
                results['hubspot_error'] = str(e)

        return results
