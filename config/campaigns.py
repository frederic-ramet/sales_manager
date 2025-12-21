"""
Configuration des campagnes et segments.

Définit les presets de campagne et les segments ICP utilisés
pour la recherche et classification des prospects.
"""

# Segments disponibles (compatibles HubSpot)
SEGMENTS = {
    "icp_principal": {
        "label": "ICP Principal",
        "description": "Cible principale: ETI/PME 50-1000 employés, secteurs prioritaires",
        "effectif_range": (50, 1000),
        "min_class": "B",
        "color": "#22c55e",  # green
    },
    "icp_opportuniste": {
        "label": "ICP Opportuniste",
        "description": "PME en croissance 50-300 employés",
        "effectif_range": (50, 300),
        "min_class": "B",
        "color": "#3b82f6",  # blue
    },
    "test": {
        "label": "Test",
        "description": "Segment de test pour nouvelles approches",
        "effectif_range": (20, 500),
        "min_class": "C",
        "color": "#f59e0b",  # amber
    },
    "custom": {
        "label": "Custom",
        "description": "Segment personnalisé",
        "effectif_range": None,
        "min_class": None,
        "color": "#6b7280",  # gray
    },
}

# Presets de campagne
CAMPAIGN_PRESETS = {
    "audit_ia_bpi": {
        "name": "Audit IA BPI (13K€ subventionné)",
        "description": "Campagne Audit IA avec subvention BPI France",
        "target_volume": 500,
        "min_class": "B",
        "segment": "icp_principal",
        "filters": {
            "ape_groups": ["Industrie Manufacturing", "Services Professionnels"],
            "effectif_min": 50,
            "effectif_max": 1000,
            "geo": "national",
        },
        "expected_meetings": 25,  # 500 * 5% B-rate
        "icon": "🎯",
    },
    "digital_factory": {
        "name": "Digital Factory (plateforme)",
        "description": "Campagne plateforme Digital Factory - prospects ultra-qualifiés",
        "target_volume": 50,
        "min_class": "A",
        "segment": "icp_principal",
        "filters": {
            "ape_groups": ["Industrie Manufacturing"],
            "effectif_min": 100,
            "effectif_max": 1000,
            "geo": "idf",
        },
        "expected_meetings": 20,  # 50 * 40% A-rate
        "icon": "🏭",
    },
    "test_opportuniste": {
        "name": "Test PME Croissance",
        "description": "Test sur segment PME opportuniste",
        "target_volume": 100,
        "min_class": "B",
        "segment": "icp_opportuniste",
        "filters": {
            "ape_groups": ["PME Croissance"],
            "effectif_min": 50,
            "effectif_max": 300,
            "geo": "national",
        },
        "expected_meetings": 5,  # 100 * 5% B-rate
        "icon": "🧪",
    },
    "services_pro_idf": {
        "name": "Services Pro IDF",
        "description": "Cabinets conseil et services professionnels en Île-de-France",
        "target_volume": 200,
        "min_class": "B",
        "segment": "icp_principal",
        "filters": {
            "ape_groups": ["Services Professionnels"],
            "effectif_min": 50,
            "effectif_max": 500,
            "geo": "idf",
        },
        "expected_meetings": 10,
        "icon": "💼",
    },
    "sante_privee": {
        "name": "Santé Privée",
        "description": "Cliniques et établissements de santé privés",
        "target_volume": 150,
        "min_class": "B",
        "segment": "icp_principal",
        "filters": {
            "ape_groups": ["Santé Privée"],
            "effectif_min": 50,
            "effectif_max": 1000,
            "geo": "national",
        },
        "expected_meetings": 8,
        "icon": "🏥",
    },
}

# Départements IDF pour filtrage géographique
IDF_DEPARTEMENTS = ["75", "92", "93", "94", "95", "77", "78", "91"]


def get_preset(preset_id: str) -> dict:
    """Récupère un preset de campagne par ID."""
    return CAMPAIGN_PRESETS.get(preset_id)


def get_segment(segment_id: str) -> dict:
    """Récupère un segment par ID."""
    return SEGMENTS.get(segment_id)


def list_presets() -> list:
    """Liste tous les presets disponibles."""
    return [
        {"id": k, **v}
        for k, v in CAMPAIGN_PRESETS.items()
    ]


def list_segments() -> list:
    """Liste tous les segments disponibles."""
    return [
        {"id": k, **v}
        for k, v in SEGMENTS.items()
    ]
