"""
Configuration centralisée.
"""

import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Configuration de l'application."""

    # Asana
    ASANA_ACCESS_TOKEN = os.getenv('ASANA_ACCESS_TOKEN', '')
    ASANA_PROJECT_GID = os.getenv('ASANA_PROJECT_GID', '')

    # Google Sheets
    GOOGLE_CREDENTIALS_PATH = os.getenv('GOOGLE_CREDENTIALS_PATH', 'credentials.json')
    GOOGLE_SPREADSHEET_URL = os.getenv('GOOGLE_SPREADSHEET_URL', '')

    @classmethod
    def validate(cls) -> dict:
        """
        Vérifie que la configuration est complète.

        Returns:
            Dict avec statut de chaque config
        """
        return {
            'asana_token': bool(cls.ASANA_ACCESS_TOKEN),
            'asana_project': bool(cls.ASANA_PROJECT_GID),
            'google_creds': bool(cls.GOOGLE_CREDENTIALS_PATH) and os.path.exists(cls.GOOGLE_CREDENTIALS_PATH),
            'google_sheet': bool(cls.GOOGLE_SPREADSHEET_URL),
        }

    @classmethod
    def is_valid(cls) -> bool:
        """Retourne True si toute la config est valide."""
        return all(cls.validate().values())
