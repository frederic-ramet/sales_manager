"""
Tests unitaires pour le module pipeline.
"""

import pytest
from datetime import datetime
from core.pipeline import PipelineCalculator, Deal


# === Fixtures ===

@pytest.fixture
def sample_asana_tasks():
    """Retourne des tasks Asana simulées pour les tests."""
    return [
        {
            'gid': '123',
            'name': 'Deal Alpha',
            'custom_fields': [
                {'name': 'Client', 'type': 'text', 'text_value': 'Acme Corp'},
                {'name': 'Projet', 'type': 'text', 'text_value': 'Refonte SI'},
                {'name': 'Estimated value', 'type': 'number', 'number_value': 100000},
                {'name': 'Marge/Bénéfice', 'type': 'number', 'number_value': 30000},
                {'name': 'Confidence Score', 'type': 'number', 'number_value': 4},
                {'name': 'Mois de facturation prévu', 'type': 'date', 'date_value': {'date': '2024-06-15'}},
            ],
            'assignee': {'name': 'Jean Dupont'},
            'due_on': '2024-05-30',
            'memberships': [{'section': {'name': 'Négociation'}}],
        },
        {
            'gid': '456',
            'name': 'Deal Beta',
            'custom_fields': [
                {'name': 'Client', 'type': 'text', 'text_value': 'BigCo'},
                {'name': 'Projet', 'type': 'text', 'text_value': 'Migration Cloud'},
                {'name': 'Estimated value', 'type': 'number', 'number_value': 50000},
                {'name': 'Marge/Bénéfice', 'type': 'number', 'number_value': 15000},
                {'name': 'Confidence Score', 'type': 'number', 'number_value': 2},
                {'name': 'Mois de facturation prévu', 'type': 'date', 'date_value': {'date': '2024-09-01'}},
            ],
            'assignee': {'name': 'Marie Martin'},
            'due_on': '2024-08-15',
            'memberships': [{'section': {'name': 'Qualification'}}],
        },
        {
            'gid': '789',
            'name': 'Deal Gamma',
            'custom_fields': [
                {'name': 'Client', 'type': 'text', 'text_value': 'StartupXYZ'},
                {'name': 'Projet', 'type': 'text', 'text_value': 'MVP App'},
                {'name': 'Estimated value', 'type': 'number', 'number_value': 25000},
                {'name': 'Marge/Bénéfice', 'type': 'number', 'number_value': 10000},
                {'name': 'Confidence Score', 'type': 'number', 'number_value': 5},
            ],
            'assignee': None,
            'due_on': None,
            'memberships': [],
        },
    ]


@pytest.fixture
def empty_tasks():
    """Retourne une liste vide de tasks."""
    return []


# === Tests PipelineCalculator ===

class TestPipelineCalculator:

    def test_parse_tasks_creates_dataframe(self, sample_asana_tasks):
        """Vérifie que le parsing crée un DataFrame valide."""
        calc = PipelineCalculator(sample_asana_tasks)
        df = calc.parse_tasks_to_dataframe()

        assert len(df) == 3
        assert 'titre' in df.columns
        assert 'budget' in df.columns
        assert 'client' in df.columns

    def test_parse_tasks_extracts_custom_fields(self, sample_asana_tasks):
        """Vérifie l'extraction des custom fields."""
        calc = PipelineCalculator(sample_asana_tasks)
        df = calc.parse_tasks_to_dataframe()

        # Premier deal
        row = df[df['asana_gid'] == '123'].iloc[0]
        assert row['client'] == 'Acme Corp'
        assert row['projet'] == 'Refonte SI'
        assert row['budget'] == 100000
        assert row['marge'] == 30000
        assert row['confidence_score'] == 4

    def test_parse_tasks_handles_missing_fields(self, sample_asana_tasks):
        """Vérifie la gestion des champs manquants."""
        calc = PipelineCalculator(sample_asana_tasks)
        df = calc.parse_tasks_to_dataframe()

        # Deal Gamma n'a pas de mois facturation
        row = df[df['asana_gid'] == '789'].iloc[0]
        assert row['owner'] is None
        assert row['section'] is None

    def test_calculate_metrics_probabilite(self, sample_asana_tasks):
        """Vérifie le calcul de probabilité."""
        calc = PipelineCalculator(sample_asana_tasks)
        calc.parse_tasks_to_dataframe()
        df = calc.calculate_metrics()

        # Confidence 4 → 70%
        row_alpha = df[df['asana_gid'] == '123'].iloc[0]
        assert row_alpha['probabilite_pct'] == 70

        # Confidence 2 → 25%
        row_beta = df[df['asana_gid'] == '456'].iloc[0]
        assert row_beta['probabilite_pct'] == 25

        # Confidence 5 → 90%
        row_gamma = df[df['asana_gid'] == '789'].iloc[0]
        assert row_gamma['probabilite_pct'] == 90

    def test_calculate_metrics_revenue_pondere(self, sample_asana_tasks):
        """Vérifie le calcul du revenue pondéré."""
        calc = PipelineCalculator(sample_asana_tasks)
        calc.parse_tasks_to_dataframe()
        df = calc.calculate_metrics()

        # Deal Alpha: 100000 × 70% = 70000
        row = df[df['asana_gid'] == '123'].iloc[0]
        assert row['revenue_pondere'] == 70000

        # Deal Beta: 50000 × 25% = 12500
        row = df[df['asana_gid'] == '456'].iloc[0]
        assert row['revenue_pondere'] == 12500

    def test_calculate_metrics_marge_pct(self, sample_asana_tasks):
        """Vérifie le calcul de marge %."""
        calc = PipelineCalculator(sample_asana_tasks)
        calc.parse_tasks_to_dataframe()
        df = calc.calculate_metrics()

        # Deal Alpha: 30000 / 100000 = 30%
        row = df[df['asana_gid'] == '123'].iloc[0]
        assert row['marge_pct'] == 30.0

    def test_calculate_metrics_scenarios(self, sample_asana_tasks):
        """Vérifie les flags de scénarios."""
        calc = PipelineCalculator(sample_asana_tasks)
        calc.parse_tasks_to_dataframe()
        df = calc.calculate_metrics()

        # Deal Alpha (conf 4): conservateur=True, probable=True
        row = df[df['asana_gid'] == '123'].iloc[0]
        assert row['scenario_conservateur'] == True
        assert row['scenario_probable'] == True

        # Deal Beta (conf 2): conservateur=False, probable=False
        row = df[df['asana_gid'] == '456'].iloc[0]
        assert row['scenario_conservateur'] == False
        assert row['scenario_probable'] == False

        # Deal Gamma (conf 5): conservateur=True, probable=True
        row = df[df['asana_gid'] == '789'].iloc[0]
        assert row['scenario_conservateur'] == True
        assert row['scenario_probable'] == True

    def test_get_summary_metrics(self, sample_asana_tasks):
        """Vérifie les métriques agrégées."""
        calc = PipelineCalculator(sample_asana_tasks)
        calc.parse_tasks_to_dataframe()
        calc.calculate_metrics()
        summary = calc.get_summary_metrics()

        assert summary['total_deals'] == 3
        assert summary['total_budget'] == 175000  # 100k + 50k + 25k
        assert summary['deals_conservateur'] == 2  # Alpha et Gamma
        assert summary['deals_probable'] == 2  # Alpha et Gamma

    def test_prepare_sheets_data(self, sample_asana_tasks):
        """Vérifie la préparation des données pour Sheets."""
        calc = PipelineCalculator(sample_asana_tasks)
        calc.parse_tasks_to_dataframe()
        calc.calculate_metrics()
        sheets_data = calc.prepare_sheets_data()

        assert 'Pipeline complet' in sheets_data
        assert 'Scénario conservateur' in sheets_data
        assert 'Scénario probable' in sheets_data
        assert 'Config' in sheets_data

        assert len(sheets_data['Pipeline complet']) == 3
        assert len(sheets_data['Scénario conservateur']) == 2  # conf >= 4
        assert len(sheets_data['Scénario probable']) == 2  # conf >= 3

    def test_empty_tasks(self, empty_tasks):
        """Vérifie le comportement avec une liste vide."""
        calc = PipelineCalculator(empty_tasks)
        df = calc.parse_tasks_to_dataframe()

        assert len(df) == 0
        assert df.empty


class TestParseCustomFields:

    def test_parse_text_field(self):
        """Vérifie le parsing des champs texte."""
        calc = PipelineCalculator([])
        result = calc._parse_custom_fields([
            {'name': 'Client', 'type': 'text', 'text_value': 'Test Corp'}
        ])
        assert result['Client'] == 'Test Corp'

    def test_parse_number_field(self):
        """Vérifie le parsing des champs numériques."""
        calc = PipelineCalculator([])
        result = calc._parse_custom_fields([
            {'name': 'Budget', 'type': 'number', 'number_value': 50000}
        ])
        assert result['Budget'] == 50000

    def test_parse_enum_field(self):
        """Vérifie le parsing des champs enum."""
        calc = PipelineCalculator([])
        result = calc._parse_custom_fields([
            {'name': 'Status', 'type': 'enum', 'enum_value': {'name': 'Active'}}
        ])
        assert result['Status'] == 'Active'

    def test_parse_date_field(self):
        """Vérifie le parsing des champs date."""
        calc = PipelineCalculator([])
        result = calc._parse_custom_fields([
            {'name': 'Date', 'type': 'date', 'date_value': {'date': '2024-06-15'}}
        ])
        assert result['Date'] == '2024-06-15'

    def test_parse_null_values(self):
        """Vérifie la gestion des valeurs nulles."""
        calc = PipelineCalculator([])
        result = calc._parse_custom_fields([
            {'name': 'Empty', 'type': 'text', 'text_value': None}
        ])
        assert result['Empty'] is None


class TestParseConfidence:

    def test_parse_numeric_confidence(self):
        """Vérifie le parsing de confidence numérique."""
        calc = PipelineCalculator([])
        assert calc._parse_confidence(4) == 4
        assert calc._parse_confidence(4.0) == 4
        assert calc._parse_confidence('3') == 3

    def test_parse_text_confidence(self):
        """Vérifie le parsing de confidence textuelle."""
        calc = PipelineCalculator([])
        assert calc._parse_confidence('high') == 4
        assert calc._parse_confidence('High') == 4
        assert calc._parse_confidence('medium') == 3
        assert calc._parse_confidence('low') == 2

    def test_parse_invalid_confidence(self):
        """Vérifie la gestion des valeurs invalides."""
        calc = PipelineCalculator([])
        assert calc._parse_confidence(None) is None
        assert calc._parse_confidence(0) is None
        assert calc._parse_confidence(10) is None
        assert calc._parse_confidence('unknown') is None
