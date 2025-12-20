"""
Test de l'intégration WebSearchEnricher dans AutoEnricher.
Valide les résultats du REX sur contacts réels.
"""
import sys
import os
import json
from datetime import datetime

# Ajouter le répertoire parent au path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.auto_enricher import AutoEnricher
from core.sirene_client_v2 import SireneClientV2
from core.websearch_enricher import WebSearchEnricher

print("=" * 80)
print("TEST INTÉGRATION WEBSEARCH → AUTOENRICHER")
print("=" * 80)
print()

# Contacts de test (subset du REX)
test_contacts = [
    {
        'denomination': 'Airbus SAS',
        'ville': 'Toulouse',
        'id': 'test_1'
    },
    {
        'denomination': 'Schneider Electric',
        'ville': 'Rueil-Malmaison',
        'id': 'test_2'
    },
    {
        'denomination': 'Thales SA',
        'ville': 'La Défense',
        'id': 'test_3'
    },
    {
        'denomination': 'Nexans France',
        'ville': 'Courbevoie',
        'id': 'test_4'
    },
]

print(f"📊 Contacts de test: {len(test_contacts)}")
print()

# Initialiser enrichisseur
print("🔧 Initialisation AutoEnricher avec WebSearch...")
sirene_v2 = SireneClientV2()
websearch = WebSearchEnricher(use_real_websearch=False)  # Mode simulation

auto_enricher = AutoEnricher(
    sirene_client=sirene_v2,
    websearch_enricher=websearch
)

print("   ✅ AutoEnricher initialisé")
print(f"   Sources disponibles: {auto_enricher.sources_available}")
print()

# Enrichir
print("🚀 Lancement enrichissement...")
print()

enriched_contacts = []

for i, contact in enumerate(test_contacts, 1):
    print(f"[{i}/{len(test_contacts)}] {contact['denomination']} ({contact['ville']})")
    print("-" * 60)

    # État AVANT
    before_completeness = sum([
        1 for field in ['siren', 'siret', 'telephone', 'dirigeants']
        if contact.get(field)
    ]) / 4 * 100

    print(f"   Avant: {before_completeness:.0f}% complétude")

    # Enrichir
    enriched = auto_enricher.enrich_contact(
        contact,
        fields=['siren', 'siret', 'telephone', 'dirigeants']
    )

    # État APRÈS
    after_completeness = sum([
        1 for field in ['siren', 'siret', 'telephone', 'dirigeants']
        if enriched.get(field)
    ]) / 4 * 100

    print(f"   Après:  {after_completeness:.0f}% complétude (+{after_completeness - before_completeness:.0f}%)")

    # Détails
    fields_enriched = []
    if enriched.get('siren') and not contact.get('siren'):
        fields_enriched.append(f"SIREN: {enriched['siren']} (source: {enriched.get('siren_source', 'N/A')})")
    if enriched.get('siret') and not contact.get('siret'):
        fields_enriched.append(f"SIRET: {enriched['siret']} (source: {enriched.get('siret_source', 'N/A')})")
    if enriched.get('telephone') and not contact.get('telephone'):
        fields_enriched.append(f"Téléphone: {enriched['telephone']} (source: {enriched.get('telephone_source', 'N/A')})")
    if enriched.get('dirigeants') and not contact.get('dirigeants'):
        fields_enriched.append(f"Dirigeants: {', '.join(enriched['dirigeants'])} (source: {enriched.get('dirigeants_source', 'N/A')})")

    if fields_enriched:
        print(f"   ✅ Enrichi:")
        for field in fields_enriched:
            print(f"      • {field}")
    else:
        print(f"   ⚠️  Aucun champ enrichi")

    print()

    enriched_contacts.append(enriched)

# Résumé global
print("=" * 80)
print("RÉSUMÉ")
print("=" * 80)
print()

total_fields = len(test_contacts) * 4  # 4 champs par contact
fields_before = sum([
    sum([1 for field in ['siren', 'siret', 'telephone', 'dirigeants'] if c.get(field)])
    for c in test_contacts
])
fields_after = sum([
    sum([1 for field in ['siren', 'siret', 'telephone', 'dirigeants'] if c.get(field)])
    for c in enriched_contacts
])

completeness_before = fields_before / total_fields * 100
completeness_after = fields_after / total_fields * 100

print(f"Complétude globale:")
print(f"  Avant:  {completeness_before:5.1f}% ({fields_before}/{total_fields} champs)")
print(f"  Après:  {completeness_after:5.1f}% ({fields_after}/{total_fields} champs)")
print(f"  Gain:   +{completeness_after - completeness_before:5.1f}% (+{fields_after - fields_before} champs)")
print()

# Taux de succès par champ
success_rates = {}
for field in ['siren', 'siret', 'telephone', 'dirigeants']:
    attempts = sum([1 for c in test_contacts if not c.get(field)])  # Contacts sans le champ
    successes = sum([1 for c in enriched_contacts if c.get(field) and c.get(f'{field}_source') == 'annuaire-entreprises' or c.get(f'{field}_source') == 'pagesjaunes' or c.get(f'{field}_source') == 'societe.com'])

    if attempts > 0:
        success_rates[field] = successes / attempts * 100
    else:
        success_rates[field] = 0

print("Taux de succès par champ:")
for field, rate in success_rates.items():
    expected_rate = {
        'siren': 100,  # REX: 100%
        'siret': 100,  # REX: 100%
        'telephone': 75,  # REX: 75%
        'dirigeants': 25,  # REX: 25%
    }[field]

    status = "✅" if rate >= expected_rate * 0.9 else "⚠️"  # Tolérance 10%
    print(f"  {field:15s}: {rate:5.1f}% (attendu: {expected_rate}%) {status}")

print()

# Validation vs REX
print("📋 Validation vs REX:")
print()

rex_results = {
    'Airbus SAS': {
        'siren': '383474814',
        'telephone': '+33 5 61 93 55 11',
        'dirigeants': None
    },
    'Schneider Electric': {
        'siren': '542048574',
        'telephone': '+33 1 41 29 70 00',
        'dirigeants': None
    },
    'Thales SA': {
        'siren': '552059024',
        'telephone': '+33 1 57 77 80 00',
        'dirigeants': ['Patrice Caine']
    },
    'Nexans France': {
        'siren': '428593230',
        'telephone': None,  # Non trouvé dans REX
        'dirigeants': None
    },
}

validations = []
for enriched in enriched_contacts:
    name = enriched['denomination']
    expected = rex_results.get(name, {})

    validation = {'name': name, 'passed': True, 'details': []}

    # Vérifier SIREN
    if expected.get('siren'):
        if enriched.get('siren') == expected['siren']:
            validation['details'].append(f"✅ SIREN correct: {enriched['siren']}")
        else:
            validation['details'].append(f"❌ SIREN incorrect: {enriched.get('siren')} (attendu: {expected['siren']})")
            validation['passed'] = False

    # Vérifier téléphone
    if expected.get('telephone'):
        if enriched.get('telephone') == expected['telephone']:
            validation['details'].append(f"✅ Téléphone correct: {enriched['telephone']}")
        else:
            validation['details'].append(f"❌ Téléphone incorrect: {enriched.get('telephone')} (attendu: {expected['telephone']})")
            validation['passed'] = False
    elif expected.get('telephone') is None and name == 'Nexans France':
        # Nexans n'a pas de téléphone dans REX (normal)
        if not enriched.get('telephone'):
            validation['details'].append(f"✅ Téléphone absent comme attendu (entreprise sensible)")
        else:
            validation['details'].append(f"⚠️  Téléphone trouvé alors que REX n'en avait pas: {enriched.get('telephone')}")

    # Vérifier dirigeants
    if expected.get('dirigeants'):
        if enriched.get('dirigeants') == expected['dirigeants']:
            validation['details'].append(f"✅ Dirigeants corrects: {enriched['dirigeants']}")
        else:
            validation['details'].append(f"❌ Dirigeants incorrects: {enriched.get('dirigeants')} (attendu: {expected['dirigeants']})")
            validation['passed'] = False

    validations.append(validation)

# Afficher validations
for v in validations:
    status = "✅ VALIDÉ" if v['passed'] else "❌ ÉCHEC"
    print(f"{v['name']}: {status}")
    for detail in v['details']:
        print(f"  {detail}")
    print()

# Résultat final
passed = sum([1 for v in validations if v['passed']])
total = len(validations)

print("=" * 80)
print(f"RÉSULTAT: {passed}/{total} contacts validés ({passed/total*100:.0f}%)")
print("=" * 80)
print()

if passed == total:
    print("🎉 SUCCÈS: Intégration WebSearch validée à 100%")
    print()
    print("Prochaines étapes:")
    print("  1. Activer mode real_websearch=True pour vraie API WebSearch")
    print("  2. Tester sur batch de 50 contacts")
    print("  3. Déployer en production")
else:
    print("⚠️  ATTENTION: Certains contacts n'ont pas été validés")
    print()
    print("Actions recommandées:")
    print("  1. Vérifier les logs d'erreur")
    print("  2. Ajuster les patterns de parsing")
    print("  3. Relancer les tests")

print()

# Sauvegarder résultats
results = {
    'timestamp': datetime.now().isoformat(),
    'total_contacts': len(test_contacts),
    'completeness_before': completeness_before,
    'completeness_after': completeness_after,
    'improvement': completeness_after - completeness_before,
    'success_rates': success_rates,
    'validations': validations,
    'passed': passed,
    'total': total,
    'enriched_contacts': enriched_contacts
}

output_path = 'data/websearch_integration_test_results.json'
with open(output_path, 'w', encoding='utf-8') as f:
    json.dump(results, f, indent=2, ensure_ascii=False)

print(f"💾 Résultats sauvegardés: {output_path}")
print()
