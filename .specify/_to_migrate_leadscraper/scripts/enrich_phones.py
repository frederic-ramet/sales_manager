"""
Script d'enrichissement des téléphones via Google Maps API.
Phase 2: Enrichissement téléphones multi-sources.
"""
import sys
import os
import json
import logging
from datetime import datetime
from typing import Dict, Any

# Ajouter le répertoire parent au path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.phone_enricher import PhoneEnricher
from config import GOOGLE_MAPS_API_KEY

# Configuration logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """Enrichit les téléphones des contacts HubSpot."""
    print("=" * 80)
    print("ENRICHISSEMENT TÉLÉPHONES - PHASE 2")
    print("=" * 80)
    print()

    # Vérifier clé API
    if not GOOGLE_MAPS_API_KEY or GOOGLE_MAPS_API_KEY == "your_google_maps_api_key_here":
        logger.error("❌ Clé API Google Maps non configurée")
        print()
        print("⚠️  Configuration requise:")
        print("   1. Obtenez une clé API Google Maps sur: https://console.cloud.google.com/")
        print("   2. Activez l'API 'Places API'")
        print("   3. Ajoutez la clé dans .env:")
        print("      GOOGLE_MAPS_API_KEY=votre_clé_ici")
        print()
        print("💰 Coût estimé: ~$17 pour 1000 contacts (avec quota gratuit: $200/mois)")
        print()
        return

    # Charger les contacts
    mirror_path = "data/hubspot_mirror.json"
    if not os.path.exists(mirror_path):
        logger.error(f"❌ Fichier non trouvé: {mirror_path}")
        print()
        print("💡 Synchronisez d'abord vos contacts HubSpot:")
        print("   streamlit run 1_🏠_Accueil.py")
        print("   Puis allez dans '📋 Mes Leads HubSpot' > 'Synchroniser'")
        return

    with open(mirror_path, 'r', encoding='utf-8') as f:
        mirror_data = json.load(f)

    contacts = mirror_data.get('contacts', [])
    total_contacts = len(contacts)

    if total_contacts == 0:
        logger.error("❌ Aucun contact à enrichir")
        return

    # Stats avant enrichissement
    contacts_with_phone = sum(1 for c in contacts if c.get('telephone'))
    contacts_without_phone = total_contacts - contacts_with_phone

    print(f"📊 Statistiques initiales:")
    print(f"   Total contacts: {total_contacts}")
    print(f"   Avec téléphone: {contacts_with_phone} ({contacts_with_phone/total_contacts*100:.1f}%)")
    print(f"   Sans téléphone: {contacts_without_phone} ({contacts_without_phone/total_contacts*100:.1f}%)")
    print()

    # Demander confirmation
    print(f"⚠️  Vous allez enrichir {contacts_without_phone} contacts")
    print(f"💰 Coût estimé: ${contacts_without_phone * 0.017:.2f} (hors quota gratuit)")
    print()
    response = input("Continuer? (oui/non): ")
    if response.lower() not in ['oui', 'o', 'yes', 'y']:
        print("Annulé.")
        return

    print()
    print("🚀 Lancement de l'enrichissement...")
    print()

    # Enrichir
    with PhoneEnricher(GOOGLE_MAPS_API_KEY) as enricher:
        enriched_contacts = enricher.enrich_batch(contacts)

    # Stats après enrichissement
    contacts_with_phone_after = sum(1 for c in enriched_contacts if c.get('telephone'))
    new_phones = contacts_with_phone_after - contacts_with_phone

    print()
    print("=" * 80)
    print("RÉSULTATS")
    print("=" * 80)
    print(f"✅ Contacts traités: {total_contacts}")
    print(f"📞 Nouveaux téléphones: {new_phones}")
    print(f"📊 Taux téléphones: {contacts_with_phone/total_contacts*100:.1f}% → {contacts_with_phone_after/total_contacts*100:.1f}%")
    print(f"🎯 Amélioration: +{(contacts_with_phone_after-contacts_with_phone)/total_contacts*100:.1f}%")
    print()

    # Breakdown par source
    sources = {}
    for c in enriched_contacts:
        source = c.get('telephone_source', 'existing')
        sources[source] = sources.get(source, 0) + 1

    if len(sources) > 1:  # Plus que 'existing'
        print("📊 Répartition par source:")
        for source, count in sorted(sources.items(), key=lambda x: x[1], reverse=True):
            print(f"   {source}: {count} ({count/contacts_with_phone_after*100:.1f}%)")
        print()

    # Sauvegarder
    output_path = "data/hubspot_mirror_phones.json"
    mirror_data['contacts'] = enriched_contacts
    mirror_data['last_phone_enrichment'] = datetime.now().isoformat()
    mirror_data['phone_enrichment_stats'] = {
        'total_contacts': total_contacts,
        'phones_before': contacts_with_phone,
        'phones_after': contacts_with_phone_after,
        'new_phones': new_phones,
        'improvement_pct': (contacts_with_phone_after-contacts_with_phone)/total_contacts*100,
        'sources': sources
    }

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(mirror_data, f, indent=2, ensure_ascii=False)

    print(f"💾 Résultats sauvegardés: {output_path}")
    print()
    print("🎉 Enrichissement téléphones terminé !")
    print()
    print("📝 Prochaines étapes:")
    print("   1. Vérifiez les résultats dans l'interface Streamlit")
    print("   2. Synchronisez avec HubSpot pour mettre à jour les contacts")
    print("   3. Utilisez les nouveaux téléphones pour vos campagnes")
    print()


if __name__ == "__main__":
    main()
