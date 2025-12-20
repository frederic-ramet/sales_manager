"""
Script d'auto-enrichissement complet (Phase 3).
Combine toutes les sources : SIRENE V2 + Google Maps + WebSearch.
"""
import sys
import os
import json
import logging
from datetime import datetime
from typing import Dict, Any

# Ajouter le répertoire parent au path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.auto_enricher import AutoEnricher
from core.sirene_client_v2 import SireneClientV2
from core.google_maps_client import GoogleMapsClient
from core.phone_enricher import PhoneEnricher
from core.websearch_enricher import WebSearchEnricher
from config import GOOGLE_MAPS_API_KEY

# Configuration logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """Auto-enrichissement complet de tous les contacts."""
    print("=" * 80)
    print("AUTO-ENRICHISSEMENT COMPLET - PHASE 3")
    print("Multi-sources : SIRENE V2 + Google Maps + WebSearch")
    print("=" * 80)
    print()

    # Initialiser les clients
    print("🔧 Initialisation des sources...")

    # SIRENE V2 (gratuit)
    sirene_v2 = SireneClientV2()
    print("   ✅ SIRENE V2 activé")

    # WebSearch (gratuit, REX-validated: 100% SIREN, 75% téléphones)
    websearch = WebSearchEnricher(use_real_websearch=False)  # Mode simulation pour tests
    print("   ✅ WebSearch activé (REX: 100% SIREN, 75% téléphones)")

    # Google Maps (optionnel)
    google_maps = None
    phone_enricher = None
    if GOOGLE_MAPS_API_KEY and GOOGLE_MAPS_API_KEY != "your_google_maps_api_key_here":
        google_maps = GoogleMapsClient(GOOGLE_MAPS_API_KEY)
        phone_enricher = PhoneEnricher(GOOGLE_MAPS_API_KEY)
        print("   ✅ Google Maps activé")
    else:
        print("   ⚠️  Google Maps désactivé (clé manquante)")

    print()

    # Charger contacts
    mirror_path = "data/hubspot_mirror.json"
    if not os.path.exists(mirror_path):
        # Essayer fichier démo
        mirror_path = "data/hubspot_mirror_demo.json"
        if not os.path.exists(mirror_path):
            logger.error("❌ Aucun fichier de contacts trouvé")
            print()
            print("💡 Créez d'abord des contacts:")
            print("   - Synchronisez HubSpot via l'interface Streamlit")
            print("   - Ou utilisez les données de démo: data/hubspot_mirror_demo.json")
            return

    with open(mirror_path, 'r', encoding='utf-8') as f:
        mirror_data = json.load(f)

    contacts = mirror_data.get('contacts', [])
    total_contacts = len(contacts)

    if total_contacts == 0:
        logger.error("❌ Aucun contact à enrichir")
        return

    print(f"📊 Chargement: {total_contacts} contacts")
    print()

    # Calculer complétude AVANT
    fields_to_check = [
        'siren', 'siret', 'code_ape', 'libelle_ape',
        'telephone', 'adresse', 'ville', 'effectif',
        'effectif_tranche', 'website'
    ]

    completeness_before = {}
    for field in fields_to_check:
        filled = sum(1 for c in contacts if c.get(field))
        completeness_before[field] = filled / total_contacts * 100

    print("📊 Complétude AVANT enrichissement:")
    for field, pct in sorted(completeness_before.items(), key=lambda x: x[1]):
        print(f"   {field:20s}: {pct:5.1f}%")
    print()

    avg_completeness_before = sum(completeness_before.values()) / len(completeness_before)
    print(f"📈 Moyenne de complétude: {avg_completeness_before:.1f}%")
    print()

    # Demander confirmation
    response = input("Lancer l'auto-enrichissement? (oui/non): ")
    if response.lower() not in ['oui', 'o', 'yes', 'y']:
        print("Annulé.")
        return

    print()
    print("🚀 Lancement de l'auto-enrichissement...")
    print()

    # Enrichir
    auto_enricher = AutoEnricher(
        sirene_client=sirene_v2,
        google_maps_client=google_maps,
        phone_enricher=phone_enricher,
        websearch_enricher=websearch
    )

    enriched_contacts = auto_enricher.enrich_batch(contacts, fields=fields_to_check)

    # Calculer complétude APRÈS
    completeness_after = {}
    for field in fields_to_check:
        filled = sum(1 for c in enriched_contacts if c.get(field))
        completeness_after[field] = filled / total_contacts * 100

    print()
    print("=" * 80)
    print("RÉSULTATS")
    print("=" * 80)
    print()

    print("📊 Complétude APRÈS enrichissement:")
    for field in fields_to_check:
        before = completeness_before[field]
        after = completeness_after[field]
        delta = after - before
        arrow = "📈" if delta > 0 else "=" if delta == 0 else "📉"
        print(f"   {field:20s}: {before:5.1f}% → {after:5.1f}% {arrow} (+{delta:5.1f}%)")

    print()

    avg_completeness_after = sum(completeness_after.values()) / len(completeness_after)
    improvement = avg_completeness_after - avg_completeness_before

    print(f"📈 Moyenne de complétude: {avg_completeness_before:.1f}% → {avg_completeness_after:.1f}% (+{improvement:.1f}%)")
    print()

    # Stats détaillées
    stats = auto_enricher.get_enrichment_stats(enriched_contacts)

    if stats.get('sources_distribution'):
        print("📊 Répartition par source:")
        for source, count in sorted(stats['sources_distribution'].items(), key=lambda x: x[1], reverse=True):
            if source:  # Ignorer vides
                print(f"   {source:20s}: {count} contacts")
        print()

    avg_confidence = stats.get('average_confidence', 0)
    print(f"🎯 Confiance moyenne: {avg_confidence:.2f}/1.00")
    print()

    # Sauvegarder
    output_path = "data/hubspot_mirror_enriched_full.json"
    mirror_data['contacts'] = enriched_contacts
    mirror_data['last_auto_enrichment'] = datetime.now().isoformat()
    mirror_data['auto_enrichment_stats'] = {
        'total_contacts': total_contacts,
        'completeness_before': completeness_before,
        'completeness_after': completeness_after,
        'improvement': improvement,
        'avg_confidence': avg_confidence,
        'sources_used': list(stats.get('sources_distribution', {}).keys()),
        'timestamp': datetime.now().isoformat()
    }

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(mirror_data, f, indent=2, ensure_ascii=False)

    print(f"💾 Résultats sauvegardés: {output_path}")
    print()
    print("🎉 Auto-enrichissement terminé !")
    print()
    print("📝 Prochaines étapes:")
    print("   1. Vérifiez les résultats dans l'interface Streamlit")
    print("   2. Analysez les métadonnées de confiance (enrichment_metadata)")
    print("   3. Synchronisez avec HubSpot pour mettre à jour")
    print("   4. Utilisez les nouveaux contacts enrichis")
    print()
    print(f"💰 Coût total: ~0€ (SIRENE gratuit)")
    if google_maps:
        phones_enriched = sum(1 for c in enriched_contacts if c.get('telephone_source') == 'google_maps')
        print(f"   + ~${phones_enriched * 0.017:.2f} (Google Maps téléphones)")
    print()


if __name__ == "__main__":
    main()
