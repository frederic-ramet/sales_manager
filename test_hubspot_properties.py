"""
Test script pour vérifier et créer les propriétés custom HubSpot.
Lance ce script pour diagnostiquer les problèmes de permissions.
"""
import logging
from dotenv import load_dotenv
from modules.lead_scraper.hubspot_client import HubSpotClient

# Configuration logging détaillé
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

def main():
    load_dotenv()

    print("\n" + "="*60)
    print("Test de création des propriétés custom HubSpot")
    print("="*60 + "\n")

    try:
        with HubSpotClient() as client:
            # 1. Vérifier les propriétés existantes
            print("1️⃣  Vérification des propriétés existantes...")
            existing = client.get_existing_properties()
            print(f"   ✅ {len(existing)} propriétés trouvées\n")

            # 2. Tenter de créer les propriétés manquantes
            print("2️⃣  Création des propriétés custom...")
            result = client.ensure_custom_properties()

            print(f"\n📊 Résultats:")
            print(f"   ✅ Existantes: {len(result['existing'])} - {result['existing']}")
            print(f"   ✨ Créées: {len(result['created'])} - {result['created']}")
            print(f"   ❌ Échecs: {len(result['failed'])} - {result['failed']}")

            if result['failed']:
                print("\n⚠️  ATTENTION: Certaines propriétés n'ont pas pu être créées!")
                print("   Causes possibles:")
                print("   1. Token API HubSpot sans permission 'CRM Object Properties (Write)'")
                print("   2. Problème réseau/API")
                print("\n   💡 Solution:")
                print("   - Allez dans HubSpot > Settings > Integrations > Private Apps")
                print("   - Sélectionnez votre app")
                print("   - Dans 'Scopes', activez 'CRM Object Properties (Write)'")
                print("   - Régénérez le token si nécessaire")
            else:
                print("\n✅ Toutes les propriétés sont prêtes!")

    except Exception as e:
        print(f"\n❌ Erreur: {e}")
        logger.exception("Erreur détaillée:")

if __name__ == "__main__":
    main()
