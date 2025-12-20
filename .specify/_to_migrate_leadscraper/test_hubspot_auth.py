"""
Script de diagnostic pour tester l'authentification HubSpot.
Utilisé pour déboguer les problèmes avec les Personal Access Keys.
"""
import httpx
import os
from dotenv import load_dotenv

# Charger .env
load_dotenv()

# Récupérer la clé
api_key = os.getenv("HUBSPOT_API_KEY")

if not api_key or api_key == "your_hubspot_api_key_here":
    print("❌ HUBSPOT_API_KEY non configurée dans .env")
    exit(1)

print(f"🔑 Clé trouvée (longueur: {len(api_key)} caractères)")
print(f"🔑 Préfixe: {api_key[:10]}...")

# Test 1: Endpoint contacts v3
print("\n" + "="*60)
print("TEST 1: GET /crm/v3/objects/contacts (API v3)")
print("="*60)

try:
    response = httpx.get(
        "https://api.hubapi.com/crm/v3/objects/contacts",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        },
        params={"limit": 1},
        timeout=30.0
    )

    print(f"📊 Status Code: {response.status_code}")
    print(f"📋 Headers: {dict(response.headers)}")

    if response.status_code == 200:
        print("✅ Succès!")
        data = response.json()
        print(f"📊 Résultat: {data.get('total', 0)} contacts trouvés")
    else:
        print(f"❌ Erreur {response.status_code}")
        print(f"📄 Réponse: {response.text}")

except Exception as e:
    print(f"❌ Exception: {type(e).__name__}: {str(e)}")

# Test 2: Endpoint account info (pour vérifier auth)
print("\n" + "="*60)
print("TEST 2: GET /account-info/v3/details (vérification auth)")
print("="*60)

try:
    response = httpx.get(
        "https://api.hubapi.com/account-info/v3/details",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        },
        timeout=30.0
    )

    print(f"📊 Status Code: {response.status_code}")

    if response.status_code == 200:
        print("✅ Authentification valide!")
        data = response.json()
        print(f"📊 Compte: {data.get('portalId', 'N/A')}")
    else:
        print(f"❌ Erreur {response.status_code}")
        print(f"📄 Réponse: {response.text}")

except Exception as e:
    print(f"❌ Exception: {type(e).__name__}: {str(e)}")

# Test 3: Scopes disponibles
print("\n" + "="*60)
print("TEST 3: GET /oauth/v1/access-tokens/{token}")
print("="*60)

try:
    # Extraire le token de la clé (format: pat-na1-xxxxx ou autre)
    response = httpx.get(
        f"https://api.hubapi.com/oauth/v1/access-tokens/{api_key}",
        timeout=30.0
    )

    print(f"📊 Status Code: {response.status_code}")

    if response.status_code == 200:
        print("✅ Token valide!")
        data = response.json()
        print(f"📊 Scopes: {data.get('scopes', [])}")
        print(f"📊 User: {data.get('user', 'N/A')}")
    else:
        print(f"⚠️ Endpoint non supporté pour ce type de clé")
        print(f"📄 Réponse: {response.text}")

except Exception as e:
    print(f"⚠️ Exception (normal pour Personal Access Key): {type(e).__name__}")

print("\n" + "="*60)
print("DIAGNOSTIC TERMINÉ")
print("="*60)
