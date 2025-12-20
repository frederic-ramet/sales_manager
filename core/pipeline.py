"""
Logique métier du pipeline et calculs financiers.
"""

import pandas as pd
from dataclasses import dataclass
from typing import Dict, List, Optional, Any
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


@dataclass
class Deal:
    """Représentation d'un deal du pipeline."""
    gid: str
    titre: str
    client: Optional[str]
    projet: Optional[str]
    budget: float
    marge: float
    mois_facturation: Optional[datetime]
    confidence_score: Optional[int]
    section: Optional[str]
    owner: Optional[str]
    due_date: Optional[str]
    created_at: Optional[str]
    modified_at: Optional[str]


class PipelineCalculator:
    """Calculs financiers sur le pipeline."""

    # Mapping Confidence Score → Probabilité (%)
    CONFIDENCE_TO_PROBA = {
        5: 90,
        4: 70,
        3: 50,
        2: 25,
        1: 10,
        None: 0,
        0: 0,
    }

    # Noms possibles des custom fields (pour robustesse)
    FIELD_ALIASES = {
        'client': ['Client', 'Nom Client', 'Company'],
        'projet': ['Projet', 'Project', 'Nom Projet'],
        'budget': ['Estimated value', 'Budget', 'Budget (€)', 'Montant'],
        'marge': ['Marge/Bénéfice', 'Marge', 'Bénéfice', 'Margin'],
        'mois_facturation': ['Mois de facturation prévu', 'Mois facturation', 'Date facturation'],
        'confidence': ['Confidence Score', 'Confidence', 'Score'],
    }

    def __init__(self, asana_tasks: List[Dict]):
        """
        Initialise le calculateur avec les tasks Asana brutes.

        Args:
            asana_tasks: Liste des tasks depuis AsanaClient.get_project_tasks()
        """
        self.tasks = asana_tasks
        self.df: Optional[pd.DataFrame] = None

    def parse_tasks_to_dataframe(self) -> pd.DataFrame:
        """
        Transforme les tasks Asana en DataFrame standardisé.

        Returns:
            DataFrame avec colonnes normalisées
        """
        rows = []

        for task in self.tasks:
            custom_fields = self._parse_custom_fields(task.get('custom_fields', []))

            row = {
                'asana_gid': task.get('gid'),
                'titre': task.get('name', ''),
                'client': self._get_field(custom_fields, 'client'),
                'projet': self._get_field(custom_fields, 'projet'),
                'budget': self._parse_number(self._get_field(custom_fields, 'budget')),
                'marge': self._parse_number(self._get_field(custom_fields, 'marge')),
                'mois_facturation': self._get_field(custom_fields, 'mois_facturation'),
                'confidence_score': self._parse_confidence(self._get_field(custom_fields, 'confidence')),
                'section': self._get_section(task),
                'owner': task.get('assignee', {}).get('name') if task.get('assignee') else None,
                'due_date': task.get('due_on'),
                'created_at': task.get('created_at'),
                'modified_at': task.get('modified_at'),
            }
            rows.append(row)

        self.df = pd.DataFrame(rows)
        logger.info(f"Parsé {len(self.df)} deals")
        return self.df

    def calculate_metrics(self) -> pd.DataFrame:
        """
        Ajoute toutes les métriques calculées au DataFrame.

        Returns:
            DataFrame enrichi avec métriques
        """
        if self.df is None:
            raise ValueError("Appeler parse_tasks_to_dataframe() d'abord")

        df = self.df.copy()

        # Probabilité basée sur confidence score
        df['probabilite_pct'] = df['confidence_score'].map(
            lambda x: self.CONFIDENCE_TO_PROBA.get(x, 0)
        )

        # Revenue pondéré
        df['revenue_pondere'] = (df['budget'] * df['probabilite_pct'] / 100).fillna(0).round(2)

        # Marge %
        df['marge_pct'] = df.apply(
            lambda row: round((row['marge'] / row['budget']) * 100, 1)
            if row['budget'] and row['budget'] > 0 and row['marge']
            else 0,
            axis=1
        )

        # Marge pondérée
        df['marge_ponderee'] = (df['marge'] * df['probabilite_pct'] / 100).fillna(0).round(2)

        # Dimensions temporelles
        df['mois_facturation_dt'] = pd.to_datetime(df['mois_facturation'], errors='coerce')
        df['annee'] = df['mois_facturation_dt'].dt.year
        df['trimestre'] = df['mois_facturation_dt'].apply(
            lambda x: f"Q{x.quarter}" if pd.notna(x) else None
        )
        df['mois'] = df['mois_facturation_dt'].dt.strftime('%Y-%m')

        # Scénarios
        df['scenario_conservateur'] = df['confidence_score'].apply(
            lambda x: x is not None and x >= 4
        )
        df['scenario_probable'] = df['confidence_score'].apply(
            lambda x: x is not None and x >= 3
        )

        self.df = df
        return df

    def get_summary_metrics(self) -> Dict[str, Any]:
        """
        Calcule les métriques agrégées du pipeline.

        Returns:
            Dict avec les KPIs principaux
        """
        if self.df is None:
            return {}

        df = self.df

        return {
            'total_deals': len(df),
            'total_budget': df['budget'].sum(),
            'total_revenue_pondere': df['revenue_pondere'].sum(),
            'total_marge': df['marge'].sum(),
            'total_marge_ponderee': df['marge_ponderee'].sum(),
            'avg_confidence': df['confidence_score'].mean(),
            'deals_conservateur': df['scenario_conservateur'].sum(),
            'deals_probable': df['scenario_probable'].sum(),
            'revenue_conservateur': df[df['scenario_conservateur']]['budget'].sum(),
            'revenue_probable': df[df['scenario_probable']]['budget'].sum(),
        }

    def prepare_sheets_data(self) -> Dict[str, pd.DataFrame]:
        """
        Prépare les DataFrames pour chaque onglet Google Sheets.

        Returns:
            Dict avec clés = noms d'onglets, valeurs = DataFrames
        """
        if self.df is None:
            raise ValueError("Appeler calculate_metrics() d'abord")

        # Colonnes à exporter (ordre et sélection)
        export_cols = [
            'titre', 'client', 'projet', 'budget', 'marge', 'marge_pct',
            'confidence_score', 'probabilite_pct', 'revenue_pondere', 'marge_ponderee',
            'section', 'owner', 'mois', 'trimestre', 'annee', 'due_date',
            'asana_gid'
        ]

        # Garder seulement les colonnes qui existent
        available_cols = [c for c in export_cols if c in self.df.columns]
        df_export = self.df[available_cols].copy()

        # Onglet 1: Pipeline complet
        pipeline_complet = df_export.copy()

        # Onglet 2: Scénario conservateur (confidence >= 4)
        scenario_conservateur = df_export[self.df['scenario_conservateur']].copy()

        # Onglet 3: Scénario probable (confidence >= 3)
        scenario_probable = df_export[self.df['scenario_probable']].copy()

        # Onglet 4: Config/Résumé
        summary = self.get_summary_metrics()
        config_data = pd.DataFrame([
            {'Métrique': 'Dernière sync', 'Valeur': datetime.now().strftime('%Y-%m-%d %H:%M:%S')},
            {'Métrique': 'Nombre de deals', 'Valeur': summary.get('total_deals', 0)},
            {'Métrique': 'Budget total', 'Valeur': summary.get('total_budget', 0)},
            {'Métrique': 'Revenue pondéré', 'Valeur': summary.get('total_revenue_pondere', 0)},
            {'Métrique': 'Marge totale', 'Valeur': summary.get('total_marge', 0)},
            {'Métrique': 'Deals conservateur', 'Valeur': summary.get('deals_conservateur', 0)},
            {'Métrique': 'Deals probable', 'Valeur': summary.get('deals_probable', 0)},
            {'Métrique': 'Revenue conservateur', 'Valeur': summary.get('revenue_conservateur', 0)},
            {'Métrique': 'Revenue probable', 'Valeur': summary.get('revenue_probable', 0)},
        ])

        return {
            'Pipeline complet': pipeline_complet,
            'Scénario conservateur': scenario_conservateur,
            'Scénario probable': scenario_probable,
            'Config': config_data,
        }

    def _parse_custom_fields(self, custom_fields: List[Dict]) -> Dict[str, Any]:
        """
        Parse les custom fields Asana en dict {nom: valeur}.

        Args:
            custom_fields: Liste des custom fields de la task

        Returns:
            Dict avec nom du field et sa valeur
        """
        result = {}

        for cf in custom_fields or []:
            name = cf.get('name')
            if not name:
                continue

            # Déterminer la valeur selon le type
            cf_type = cf.get('type')

            if cf_type == 'number':
                value = cf.get('number_value')
            elif cf_type == 'text':
                value = cf.get('text_value')
            elif cf_type == 'enum':
                enum_value = cf.get('enum_value')
                value = enum_value.get('name') if enum_value else None
            elif cf_type == 'date':
                date_value = cf.get('date_value')
                value = date_value.get('date') if date_value else None
            else:
                # Fallback sur display_value
                value = cf.get('display_value')

            result[name] = value

        return result

    def _get_field(self, fields: Dict, field_type: str) -> Any:
        """
        Récupère une valeur avec gestion des alias de noms.

        Args:
            fields: Dict des custom fields parsés
            field_type: Type de champ (client, projet, budget, etc.)

        Returns:
            Valeur du champ ou None
        """
        aliases = self.FIELD_ALIASES.get(field_type, [])

        for alias in aliases:
            if alias in fields and fields[alias] is not None:
                return fields[alias]

        return None

    def _parse_number(self, value: Any) -> float:
        """Parse une valeur en nombre, retourne 0 si invalide."""
        if value is None:
            return 0.0
        try:
            return float(value)
        except (ValueError, TypeError):
            return 0.0

    def _parse_confidence(self, value: Any) -> Optional[int]:
        """Parse le confidence score (1-5)."""
        if value is None:
            return None
        try:
            score = int(float(value))
            return score if 1 <= score <= 5 else None
        except (ValueError, TypeError):
            # Si c'est un texte comme "High", "Medium", etc.
            text_mapping = {
                'very high': 5, 'high': 4, 'medium': 3, 'low': 2, 'very low': 1,
                'très haute': 5, 'haute': 4, 'moyenne': 3, 'basse': 2, 'très basse': 1,
            }
            if isinstance(value, str):
                return text_mapping.get(value.lower())
            return None

    def _get_section(self, task: Dict) -> Optional[str]:
        """Extrait le nom de la section (colonne board Kanban)."""
        memberships = task.get('memberships', [])
        if memberships:
            section = memberships[0].get('section', {})
            return section.get('name') if section else None
        return None
