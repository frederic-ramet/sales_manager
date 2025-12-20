#!/usr/bin/env python3
"""
Script de test des APIs SIRENE et Pappers
"""

import sys
sys.path.insert(0, '.')

from core.sirene_client import SireneClient
from core.pappers_client import PappersClient
import config

print("╔" + "="*60 + "╗")
print("║" + " "*15 + "TEST DES APIS" + " "*32 + "║")
print("╚" + "="*60 + "╝")
print()

# Test 1: API SIRENE
print("🔍 Test API SIRENE")
print("-" * 62)

try:
    with SireneClient() as client:
        print(f"✓ Client SIRENE initialisé")
        print(f"  Base URL: {client.base_url}")

        # Test recherche simple
        print("\n→ Test recherche avec code APE 62.01Z (Programmation informatique)")
        companies = client.search(
            codes_ape=["62.01Z"],
            page=1,
            per_page=5
        )

        print(f"✓ Requête réussie!")
        print(f"  Total résultats: {companies['total_results']}")
        print(f"  Résultats page 1: {len(companies['results'])}")

        if companies['results']:
            print(f"\n→ Exemple entreprise:")
            example = companies['results'][0]
            print(f"  SIREN: {example['siren']}")
            print(f"  Nom: {example['denomination']}")
            print(f"  Ville: {example['ville']}")
            print(f"  Code APE: {example['code_ape']}")
            print(f"  Activité: {example['libelle_ape']}")

        print("\n✅ API SIRENE fonctionne correctement!")

except Exception as e:
    print(f"❌ Erreur API SIRENE: {e}")
    import traceback
    traceback.print_exc()

print()

# Test 2: API Pappers
print("💎 Test API Pappers")
print("-" * 62)

if not config.PAPPERS_API_KEY or config.PAPPERS_API_KEY == "your_api_key_here":
    print("⚠️  Clé API Pappers non configurée")
    print("   Configurez PAPPERS_API_KEY dans .env pour tester")
else:
    try:
        with PappersClient() as client:
            print(f"✓ Client Pappers initialisé")

            # Test avec un SIREN connu (Google France)
            test_siren = "443061841"
            print(f"\n→ Test avec SIREN {test_siren} (Google France)")

            data = client.get_company(test_siren)

            if data:
                print(f"✓ Requête réussie!")

                contact = client.extract_contact_info(data)

                print(f"\n→ Informations extraites:")
                if contact['dirigeant_nom']:
                    print(f"  Dirigeant: {contact['dirigeant_prenom']} {contact['dirigeant_nom']}")
                    print(f"  Fonction: {contact['dirigeant_fonction']}")
                if contact['email']:
                    print(f"  Email: {contact['email']}")
                if contact['telephone']:
                    print(f"  Téléphone: {contact['telephone']}")
                if contact['site_web']:
                    print(f"  Site: {contact['site_web']}")

                print(f"\n  Crédits utilisés: {client.get_request_count()}")
                print("\n✅ API Pappers fonctionne correctement!")
            else:
                print(f"⚠️  Aucune donnée retournée (entreprise peut-être introuvable)")

    except Exception as e:
        print(f"❌ Erreur API Pappers: {e}")
        import traceback
        traceback.print_exc()

print()
print("=" * 62)
print("Tests terminés!")
print("=" * 62)
