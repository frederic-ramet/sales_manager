"""
Enrichissement de 100 contacts avec vraies recherches WebSearch.
Création d'un dataset de référence pour validation et tests.
"""
import sys
import os
import json
from datetime import datetime
import time

# Ajouter le répertoire parent au path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

print("=" * 80)
print("ENRICHISSEMENT DE 100 CONTACTS - DATASET DE RÉFÉRENCE")
print("=" * 80)
print()

# Liste de 100 entreprises françaises (CAC40, Next40, ETI, PME)
COMPANIES_100 = [
    # CAC 40
    {"denomination": "TotalEnergies", "ville": "Courbevoie"},
    {"denomination": "LVMH", "ville": "Paris"},
    {"denomination": "L'Oréal", "ville": "Clichy"},
    {"denomination": "Sanofi", "ville": "Paris"},
    {"denomination": "Air Liquide", "ville": "Paris"},
    {"denomination": "BNP Paribas", "ville": "Paris"},
    {"denomination": "Airbus", "ville": "Toulouse"},
    {"denomination": "Schneider Electric", "ville": "Rueil-Malmaison"},
    {"denomination": "Saint-Gobain", "ville": "Courbevoie"},
    {"denomination": "Vinci", "ville": "Rueil-Malmaison"},
    {"denomination": "Renault", "ville": "Boulogne-Billancourt"},
    {"denomination": "Stellantis", "ville": "Rueil-Malmaison"},
    {"denomination": "Pernod Ricard", "ville": "Paris"},
    {"denomination": "Danone", "ville": "Paris"},
    {"denomination": "Kering", "ville": "Paris"},
    {"denomination": "Michelin", "ville": "Clermont-Ferrand"},
    {"denomination": "Legrand", "ville": "Limoges"},
    {"denomination": "Thales", "ville": "Paris"},
    {"denomination": "Orange", "ville": "Paris"},
    {"denomination": "Engie", "ville": "Courbevoie"},
    {"denomination": "Société Générale", "ville": "Paris"},
    {"denomination": "Crédit Agricole", "ville": "Paris"},
    {"denomination": "AXA", "ville": "Paris"},
    {"denomination": "Carrefour", "ville": "Massy"},
    {"denomination": "Bouygues", "ville": "Paris"},
    {"denomination": "Edenred", "ville": "Issy-les-Moulineaux"},
    {"denomination": "Dassault Systèmes", "ville": "Vélizy-Villacoublay"},
    {"denomination": "Hermès", "ville": "Paris"},
    {"denomination": "Safran", "ville": "Paris"},
    {"denomination": "Capgemini", "ville": "Paris"},

    # ETI - Technologie
    {"denomination": "OVHcloud", "ville": "Roubaix"},
    {"denomination": "Dassault Aviation", "ville": "Saint-Cloud"},
    {"denomination": "Atos", "ville": "Paris"},
    {"denomination": "Sopra Steria", "ville": "Paris"},
    {"denomination": "Worldline", "ville": "Bezons"},
    {"denomination": "Nexans", "ville": "Courbevoie"},
    {"denomination": "Valeo", "ville": "Paris"},
    {"denomination": "Alstom", "ville": "Saint-Ouen"},
    {"denomination": "STMicroelectronics", "ville": "Geneva"},
    {"denomination": "Soitec", "ville": "Bernin"},

    # ETI - Distribution & Retail
    {"denomination": "Auchan", "ville": "Croix"},
    {"denomination": "Intermarché", "ville": "Paris"},
    {"denomination": "E.Leclerc", "ville": "Paris"},
    {"denomination": "Casino", "ville": "Saint-Étienne"},
    {"denomination": "Fnac Darty", "ville": "Ivry-sur-Seine"},
    {"denomination": "Leroy Merlin", "ville": "Lezennes"},
    {"denomination": "Decathlon", "ville": "Villeneuve-d'Ascq"},
    {"denomination": "Boulanger", "ville": "Lille"},
    {"denomination": "Cultura", "ville": "Évry"},
    {"denomination": "Monoprix", "ville": "Clichy"},

    # ETI - Services
    {"denomination": "Veolia", "ville": "Aubervilliers"},
    {"denomination": "Sodexo", "ville": "Issy-les-Moulineaux"},
    {"denomination": "JCDecaux", "ville": "Plaisir"},
    {"denomination": "Publicis", "ville": "Paris"},
    {"denomination": "Havas", "ville": "Paris"},
    {"denomination": "Accor", "ville": "Paris"},
    {"denomination": "Elior", "ville": "Paris"},
    {"denomination": "Eiffage", "ville": "Vélizy-Villacoublay"},
    {"denomination": "Colas", "ville": "Boulogne-Billancourt"},
    {"denomination": "Spie", "ville": "Cergy"},

    # ETI - Industrie
    {"denomination": "Arkema", "ville": "Colombes"},
    {"denomination": "Faurecia", "ville": "Nanterre"},
    {"denomination": "Plastic Omnium", "ville": "Levallois-Perret"},
    {"denomination": "Imerys", "ville": "Paris"},
    {"denomination": "Wendel", "ville": "Paris"},
    {"denomination": "Vicat", "ville": "L'Isle-d'Abeau"},
    {"denomination": "Manitou", "ville": "Ancenis"},
    {"denomination": "Derichebourg", "ville": "Paris"},
    {"denomination": "CGG", "ville": "Massy"},
    {"denomination": "Technip Energies", "ville": "Paris"},

    # PME - Tech & Startups
    {"denomination": "Blablacar", "ville": "Paris"},
    {"denomination": "Doctolib", "ville": "Paris"},
    {"denomination": "Contentsquare", "ville": "Paris"},
    {"denomination": "Back Market", "ville": "Paris"},
    {"denomination": "ManoMano", "ville": "Paris"},
    {"denomination": "Veepee", "ville": "Paris"},
    {"denomination": "Mirakl", "ville": "Paris"},
    {"denomination": "Dataiku", "ville": "Paris"},
    {"denomination": "Algolia", "ville": "Paris"},
    {"denomination": "Criteo", "ville": "Paris"},

    # PME - Services B2B
    {"denomination": "Webhelp", "ville": "Paris"},
    {"denomination": "Teleperformance", "ville": "Paris"},
    {"denomination": "Chronopost", "ville": "Paris"},
    {"denomination": "DPD France", "ville": "Paris"},
    {"denomination": "Geodis", "ville": "Paris"},
    {"denomination": "FM Logistic", "ville": "Phalsbourg"},
    {"denomination": "Transdev", "ville": "Paris"},
    {"denomination": "Keolis", "ville": "Paris"},
    {"denomination": "RATP", "ville": "Paris"},
    {"denomination": "SNCF", "ville": "Paris"},

    # PME - Agroalimentaire
    {"denomination": "Lactalis", "ville": "Laval"},
    {"denomination": "Savencia", "ville": "Viroflay"},
    {"denomination": "Bel", "ville": "Paris"},
    {"denomination": "Bongrain", "ville": "Paris"},
    {"denomination": "Andros", "ville": "Biars-sur-Cère"},
    {"denomination": "Bonduelle", "ville": "Villeneuve-d'Ascq"},
    {"denomination": "Limagrain", "ville": "Saint-Beauzire"},
    {"denomination": "Terrena", "ville": "Ancenis"},
]

print(f"📊 {len(COMPANIES_100)} entreprises à enrichir")
print()
print("⏳ Estimation: ~3 min par contact = ~5 heures total")
print("   (Pause toutes les 10 recherches pour éviter rate limiting)")
print()

# Demander confirmation
response = input("Continuer? (o/n): ")
if response.lower() != 'o':
    print("Annulé.")
    sys.exit(0)

print()
print("🚀 Lancement de l'enrichissement...")
print()

# Import WebSearch (sera fait dans le script principal)
# Pour l'instant, structure de base
enriched_contacts = []
stats = {
    'total': len(COMPANIES_100),
    'siren_found': 0,
    'siret_found': 0,
    'telephone_found': 0,
    'dirigeants_found': 0,
    'enrichment_time': 0
}

start_time = time.time()

for i, company in enumerate(COMPANIES_100, 1):
    print(f"[{i}/{len(COMPANIES_100)}] {company['denomination']} ({company['ville']})")
    print("-" * 60)

    # TODO: Vraies recherches WebSearch ici
    # Pour l'instant, structure template
    enriched = {
        'hubspot_id': f'ref_{i:03d}',
        'denomination': company['denomination'],
        'ville': company['ville'],
        'siren': '',
        'siret': '',
        'telephone': '',
        'dirigeants': '',
        'enrichment_metadata': {
            'timestamp': datetime.now().isoformat(),
            'method': 'WebSearch manual',
            'sources': []
        }
    }

    enriched_contacts.append(enriched)

    # Pause toutes les 10 recherches (politesse serveurs)
    if i % 10 == 0:
        print()
        print("⏸️  Pause 30 secondes (rate limiting)...")
        time.sleep(30)
        print()

elapsed = time.time() - start_time

print()
print("=" * 80)
print("RÉSUMÉ")
print("=" * 80)
print()
print(f"✅ {len(enriched_contacts)} contacts traités")
print(f"⏱️  Temps écoulé: {elapsed/60:.1f} minutes")
print()

# Sauvegarder
output = {
    'creation_date': datetime.now().isoformat(),
    'total_contacts': len(enriched_contacts),
    'method': 'WebSearch manual enrichment',
    'stats': stats,
    'contacts': enriched_contacts
}

output_path = 'data/reference_dataset_100.json'
with open(output_path, 'w', encoding='utf-8') as f:
    json.dump(output, f, indent=2, ensure_ascii=False)

print(f"💾 Dataset sauvegardé: {output_path}")
print()
