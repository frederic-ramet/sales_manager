#!/usr/bin/env python3
"""
Migration des contacts vers format V2.

Enrichit les contacts existants avec:
- SIRET siège social
- Libellé APE complet
- Effectif par tranches
- Multi-dirigeants (via Pappers si configuré)

Usage:
    python scripts/migrate_to_v2.py
"""

import sys
sys.path.insert(0, '/home/user/leadscraper')

import json
from pathlib import Path
from core.sirene_client_v2 import SireneClientV2
from config import PAPPERS_API_KEY

print("=" * 80)
print("MIGRATION CONTACTS VERS FORMAT V2")
print("=" * 80)

# Charger les contacts
mirror_path = Path("data/hubspot_mirror.json")

if not mirror_path.exists():
    print(f"❌ Fichier {mirror_path} introuvable")
    sys.exit(1)

with open(mirror_path, 'r') as f:
    mirror_data = json.load(f)

contacts = mirror_data.get('contacts', [])
total = len(contacts)

print(f"\n📊 {total} contacts à traiter")

# Initialiser clients
sirene_v2 = SireneClientV2()

# Pappers optionnel
pappers = None
if PAPPERS_API_KEY and PAPPERS_API_KEY != "your_api_key_here":
    try:
        from core.pappers_client import PappersClient
        pappers = PappersClient(PAPPERS_API_KEY)
        print("✅ Pappers configuré (dirigeants seront enrichis)")
    except:
        print("⚠️  Pappers non disponible (dirigeants non enrichis)")
else:
    print("⚠️  Pappers non configuré (dirigeants non enrichis)")

# Statistiques
stats = {
    'total': total,
    'with_siren': 0,
    'enriched_siret': 0,
    'enriched_libelle_ape': 0,
    'enriched_effectif_tranche': 0,
    'enriched_dirigeants': 0,
    'errors': 0
}

# Enrichissement
print("\n🔄 Enrichissement en cours...")

for idx, contact in enumerate(contacts):
    siren = contact.get('siren', '').strip()

    if not siren:
        continue

    stats['with_siren'] += 1

    try:
        # Récupérer données complètes
        full_data = sirene_v2.get_full_company_data(siren)

        if full_data:
            # SIRET
            if full_data.get('siret_siege'):
                contact['siret'] = full_data['siret_siege']
                stats['enriched_siret'] += 1

            # Libellé APE
            if full_data.get('libelle_ape'):
                contact['libelle_ape'] = full_data['libelle_ape']
                stats['enriched_libelle_ape'] += 1

            # Effectif tranche
            if full_data.get('effectif_tranche'):
                contact['effectif_tranche'] = full_data['effectif_tranche']
                stats['enriched_effectif_tranche'] += 1

            # Dirigeants via Pappers si disponible
            if pappers and not contact.get('dirigeants'):
                try:
                    pappers_data = pappers.get_company_data(siren)
                    if pappers_data:
                        # Extraire dirigeants
                        dirigeants = []

                        # Représentants légaux
                        representants = pappers_data.get('representants', [])
                        for rep in representants[:3]:  # Max 3 dirigeants
                            dirigeants.append({
                                'nom': rep.get('nom', ''),
                                'prenom': rep.get('prenom', ''),
                                'fonction': rep.get('qualite', '')
                            })

                        if dirigeants:
                            contact['dirigeants'] = dirigeants
                            stats['enriched_dirigeants'] += 1
                except:
                    pass  # Pappers optionnel, continuer si échec

            # Progress
            if (idx + 1) % 50 == 0:
                progress = (idx + 1) / total * 100
                print(f"  {idx + 1}/{total} ({progress:.1f}%)")

        else:
            stats['errors'] += 1

    except Exception as e:
        stats['errors'] += 1
        print(f"  ❌ Erreur SIREN {siren}: {e}")

# Sauvegarder
output_path = Path("data/hubspot_mirror_v2.json")
mirror_data['contacts'] = contacts
mirror_data['format_version'] = 'v2'
mirror_data['v2_enrichment'] = stats

with open(output_path, 'w') as f:
    json.dump(mirror_data, f, indent=2, ensure_ascii=False)

print(f"\n✅ Sauvegardé dans {output_path}")

# Résumé
print("\n" + "=" * 80)
print("RÉSUMÉ MIGRATION")
print("=" * 80)
print(f"Total contacts: {stats['total']}")
print(f"Avec SIREN: {stats['with_siren']}")
print(f"Enrichis SIRET: {stats['enriched_siret']} ({stats['enriched_siret']/stats['with_siren']*100:.1f}%)" if stats['with_siren'] > 0 else "Enrichis SIRET: 0")
print(f"Enrichis libellé APE: {stats['enriched_libelle_ape']} ({stats['enriched_libelle_ape']/stats['with_siren']*100:.1f}%)" if stats['with_siren'] > 0 else "Enrichis libellé APE: 0")
print(f"Enrichis effectif tranche: {stats['enriched_effectif_tranche']}")
print(f"Enrichis dirigeants: {stats['enriched_dirigeants']}")
print(f"Erreurs: {stats['errors']}")

print("\n🎉 Migration V2 terminée !")
print(f"\n💡 Prochaine étape: Utiliser {output_path} au lieu de hubspot_mirror.json")
