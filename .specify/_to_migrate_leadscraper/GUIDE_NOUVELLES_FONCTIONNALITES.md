# Guide des Nouvelles Fonctionnalités

Ce guide explique comment utiliser les 5 nouvelles fonctionnalités ajoutées à l'application.

---

## 🎯 Vue d'ensemble

L'application dispose maintenant d'un **workflow complet de bout en bout** :

```
Import/Sync → Enrichissement → Scoring → Analytics → Export
```

---

## 📈 1. Analytics Dashboard

**Page :** `7_📈_Analytics.py`

### À quoi ça sert ?

Visualiser la qualité globale de votre base de contacts et identifier les opportunités d'amélioration.

### Comment l'utiliser ?

1. Synchronisez vos contacts HubSpot (depuis la page "Mes Leads HubSpot")
2. Accédez à la page **📈 Analytics**
3. Consultez les statistiques :
   - **Stats globales** : total, % avec SIREN, % avec email/téléphone
   - **Distribution scores** : combien de Hot/Warm/Cold/Frozen
   - **Taux de complétude** : pour 8 champs clés (SIREN, email, téléphone, etc.)
   - **Top secteurs** : les 10 codes APE les plus représentés
   - **Top villes** : les 10 villes les plus représentées

### Cas d'usage

**Scénario :** Vous voulez savoir combien de leads sont prêts à être contactés

1. Regardez la métrique "🔥 Hot" (score ≥ 70)
2. Si peu de Hot → identifiez les champs manquants dans "Taux de complétude"
3. Enrichissez via SIRENE ou Pappers pour améliorer les scores

---

## 🚀 2. Workflow Automatisé

**Page :** `8_🚀_Workflow_Auto.py`

### À quoi ça sert ?

Enrichir automatiquement vos contacts en **1 seul clic** : SIRENE → Pappers → HubSpot

### Comment l'utiliser ?

1. Accédez à **🚀 Workflow Auto**
2. Sélectionnez le type de contacts à enrichir :
   - **Tous** : enrichir toute la base
   - **Sans SIREN** : enrichissement SIRENE uniquement
   - **Avec SIREN mais sans dirigeant** : enrichissement Pappers uniquement
3. Vérifiez l'estimation des coûts Pappers
4. Cliquez sur **🚀 Lancer le workflow**
5. Attendez la fin (3 étapes : SIRENE → Pappers → HubSpot)
6. Consultez le résumé :
   - X enrichis SIRENE
   - Y enrichis Pappers
   - Z mis à jour dans HubSpot

### Cas d'usage

**Scénario :** Vous venez d'importer 500 contacts depuis un salon professionnel

1. Importez le CSV via **📥 Import CSV**
2. Lancez **🚀 Workflow Auto** avec "Tous"
3. Résultat :
   - 450 enrichis SIRENE (gratuit)
   - 300 enrichis Pappers (300 crédits)
   - 450 mis à jour HubSpot
   - Scores passent de 15/100 à 60/100 en moyenne

**Temps gagné :** Au lieu de 3 actions manuelles, tout se fait en 1 clic !

---

## 📥 3. Import CSV

**Page :** `9_📥_Import_CSV.py`

### À quoi ça sert ?

Importer des listes de contacts externes (salons, LinkedIn, exports CRM) et les enrichir avant de les envoyer vers HubSpot.

### Comment l'utiliser ?

1. Préparez votre fichier CSV avec au minimum :
   - Une colonne "nom" ou "entreprise"
   - Une colonne "email" (optionnel mais recommandé)

2. Accédez à **📥 Import CSV**

3. **Étape 1 : Upload**
   - Cliquez sur "Browse files"
   - Sélectionnez votre CSV
   - Vérifiez la preview (5 premières lignes)

4. **Étape 2 : Mapping**
   - Mappez chaque colonne de votre CSV vers les champs standards :
     - Nom entreprise → `denomination`
     - Email → `email`
     - Ville → `ville`
     - Téléphone → `telephone`
     - etc.

5. **Étape 3 : Options d'enrichissement**
   - ✅ Enrichir via SIRENE (gratuit)
   - ✅ Enrichir via Pappers (payant - vérifiez le coût estimé)
   - ✅ Pousser vers HubSpot après enrichissement

6. Cliquez sur **🚀 Lancer l'import**

7. **Résultats :**
   - Voir les contacts enrichis
   - Télécharger le CSV enrichi
   - Stats : X enrichis SIRENE, Y enrichis Pappers

### Cas d'usage

**Scénario :** Import de 200 contacts d'un salon B2B

**CSV initial :**
```csv
Nom,Email,Ville
Entreprise A,contact@a.fr,Paris
Entreprise B,info@b.com,Lyon
```

**Après import + enrichissement :**
```csv
Nom,Email,Ville,SIREN,Code APE,Dirigeant,Téléphone,Score
Entreprise A,contact@a.fr,Paris,123456789,6201Z,Jean Dupont,0102030405,75
Entreprise B,info@b.com,Lyon,987654321,7022Z,Marie Martin,0506070809,65
```

**Résultat :** Leads prêts à être contactés avec coordonnées dirigeants !

---

## 📝 4. Templates Export

**Page :** `10_📝_Templates_Export.py`

### À quoi ça sert ?

Exporter vos contacts dans différents formats (CSV, Excel, JSON) avec des colonnes personnalisées et des filtres avancés.

### Comment l'utiliser ?

1. Accédez à **📝 Templates Export**

2. **Méthode 1 : Templates prédéfinis**
   - **🎯 Commercial** : Nom, Email, Téléphone, Score (pour vos commerciaux)
   - **📊 Analyse** : SIREN, APE, Effectif, CA, Ville (pour analyse sectorielle)
   - **💎 Complet** : Toutes les colonnes (export full)

3. **Méthode 2 : Personnalisation**
   - Sélectionnez les colonnes à exporter (multiselect)
   - Appliquez des filtres :
     - **Score minimum** : 0, 30, 50, 70, 100
     - **Catégories** : Hot, Warm, Cold, Frozen
     - **SIREN** : Tous, Avec SIREN, Sans SIREN

4. **Preview** : Vérifiez les 10 premières lignes

5. **Export** :
   - 📥 Télécharger CSV
   - 📊 Télécharger Excel (si openpyxl installé)
   - 🗂️ Télécharger JSON

6. **Stats d'export** :
   - Nombre de contacts exportés
   - Score moyen
   - % avec SIREN / Email
   - Distribution par catégorie

### Cas d'usage

**Scénario 1 : Export pour campagne emailing**

1. Filtre : Score ≥ 50 (Hot + Warm uniquement)
2. Template : Commercial (Nom, Email, Téléphone, Score)
3. Export CSV
4. Import dans votre outil d'emailing (Mailchimp, Sendinblue, etc.)

**Résultat :** 150 contacts qualifiés avec emails valides

---

**Scénario 2 : Analyse sectorielle pour votre CEO**

1. Filtre : Tous
2. Template : Analyse (SIREN, APE, Effectif, CA, Ville)
3. Export Excel
4. Analyse dans Excel (tableaux croisés dynamiques, graphiques)

**Résultat :** Vue d'ensemble sectorielle pour décisions stratégiques

---

**Scénario 3 : Export technique pour développeurs**

1. Filtre : Tous
2. Template : Complet (toutes colonnes)
3. Export JSON
4. Import dans votre application via API

**Résultat :** Intégration technique avec vos outils internes

---

## 🎯 5. Système de Scoring

**Module :** `core/scoring.py`
**Intégré dans :** Mes Leads HubSpot, Enrichir SIRENE, Enrichir Pappers, Analytics, Templates Export

### À quoi ça sert ?

Qualifier automatiquement vos leads de 0 à 100 points selon leur complétude et leur pertinence.

### Comment ça fonctionne ?

#### Critères de scoring (100 points max)

**Critères de base :**
- Email direct (non gmail/yahoo) : **15 pts**
- Téléphone direct : **15 pts**
- Dirigeant identifié : **10 pts**
- SIREN présent : **10 pts**
- Code APE présent : **5 pts**
- Ville présente : **5 pts**
- Effectif renseigné : **10 pts**
- Chiffre d'affaires renseigné : **5 pts**

**Bonus pertinence :**
- Effectif cible (10-50 employés) : **+10 pts**
- CA significatif (> 1M€) : **+10 pts**
- Secteur B2B prioritaire : **+5 pts**

#### Catégories

- 🔥 **Hot** (≥ 70 pts) : Leads prioritaires, prêts à être contactés
- 🌡️ **Warm** (50-69 pts) : Leads qualifiés, nécessitent peu d'enrichissement
- ❄️ **Cold** (30-49 pts) : Leads à enrichir avant contact
- 🧊 **Frozen** (< 30 pts) : Leads incomplets, enrichissement urgent

### Où voir les scores ?

#### 1. Page "Mes Leads HubSpot"

- **Stats par catégorie** : combien de Hot/Warm/Cold/Frozen
- **Colonne Score** : barre de progression 0-100
- **Colonne Qualité** : 🔥/🌡️/❄️/🧊
- **Filtre** : sélectionner uniquement Hot, ou Warm, etc.

#### 2. Pages Enrichissement (SIRENE / Pappers)

- **Score avant enrichissement** : ex. 15/100
- **Score après enrichissement** : ex. 60/100
- **Amélioration visible** : (+45 pts)
- **Top 10 améliorations** : les contacts les plus améliorés

#### 3. Page Analytics

- **Distribution globale** : X% Hot, Y% Warm, etc.
- **Score moyen** : ex. 45/100
- **Évolution** : suivi dans le temps (à venir)

### Cas d'usage

**Scénario : Prioriser les appels commerciaux**

1. Accédez à "Mes Leads HubSpot"
2. Filtrez par catégorie : "🔥 Hot"
3. Résultat : 45 contacts avec score ≥ 70
4. Exportez au format "Commercial"
5. Vos commerciaux appellent en priorité ces 45 leads

**ROI :** Taux de conversion x2 en se concentrant sur les leads qualifiés !

---

**Scénario : Mesurer l'impact de l'enrichissement**

**Avant enrichissement :**
- 500 contacts
- Score moyen : 25/100
- 5% Hot (25 contacts)

**Après enrichissement SIRENE + Pappers :**
- 500 contacts
- Score moyen : 55/100 (+30 pts)
- 35% Hot (175 contacts)

**ROI visible :**
- +150 leads Hot (+600%)
- Amélioration moyenne : +30 pts
- Coût Pappers : 500 crédits (€99)
- Valeur ajoutée : 150 nouveaux leads qualifiés

---

## 📊 Workflow Complet de Bout en Bout

### Exemple : Campagne Lead Gen pour un Salon B2B

**Étape 1 : Import (📥 Import CSV)**
- Upload du fichier salon (500 contacts)
- Mapping colonnes : Nom, Email, Ville
- Score initial : 15/100 en moyenne

**Étape 2 : Enrichissement Automatique (🚀 Workflow Auto)**
- Sélection : "Tous"
- Enrichissement SIRENE : 450 SIREN trouvés (gratuit)
- Enrichissement Pappers : 300 dirigeants trouvés (300 crédits = €59)
- Score après : 55/100 en moyenne (+40 pts)

**Étape 3 : Analyse (📈 Analytics)**
- Distribution : 35% Hot, 40% Warm, 20% Cold, 5% Frozen
- Top secteur : 6201Z (Programmation informatique) - 120 contacts
- Top ville : Paris - 180 contacts

**Étape 4 : Priorisation (📝 Templates Export)**
- Filtre : Hot uniquement (175 contacts)
- Template : Commercial
- Export CSV

**Étape 5 : Action commerciale**
- Import CSV dans CRM
- Campagne emailing : 175 contacts Hot
- Appels téléphoniques : dirigeants identifiés

**Résultat final :**
- 500 contacts importés
- 450 enrichis SIRENE (90%)
- 300 enrichis Pappers (60%)
- 175 leads Hot prêts à contacter (35%)
- **Taux de conversion attendu : x3 vs leads non enrichis**

---

## 💡 Astuces & Bonnes Pratiques

### 1. Optimiser les coûts Pappers

❌ **À éviter :**
- Enrichir tous les contacts d'un coup (coûteux)

✅ **Recommandé :**
1. Enrichir SIRENE d'abord (gratuit)
2. Analyser les scores
3. Enrichir Pappers uniquement les Warm (50-69 pts) pour les passer Hot
4. Les Frozen resteront Frozen même avec Pappers

**Économie :** -50% de crédits Pappers

---

### 2. Maximiser le scoring

Pour atteindre 100/100 pts, un contact doit avoir :

✅ Email professionnel (non gmail/yahoo) : +15
✅ Téléphone direct : +15
✅ Dirigeant identifié : +10
✅ SIREN : +10
✅ Code APE : +5
✅ Ville : +5
✅ Effectif : +10
✅ CA : +5
✅ Effectif 10-50 : +10
✅ CA > 1M€ : +10
✅ Secteur B2B : +5

**Total : 100 pts = Lead parfait !**

---

### 3. Nettoyer régulièrement

**Tous les mois :**
1. Sync HubSpot
2. Analytics → identifier les Frozen
3. Décision :
   - Si < 10% Frozen → OK
   - Si > 30% Frozen → nettoyage nécessaire
4. Templates Export → Filtrer Frozen
5. Archiver ou enrichir

---

### 4. Suivre l'évolution

**Tableau de bord mensuel :**

| Mois | Total | Hot | Warm | Cold | Frozen | Score moyen |
|------|-------|-----|------|------|--------|-------------|
| Jan  | 500   | 50  | 150  | 200  | 100    | 35/100      |
| Fév  | 650   | 150 | 250  | 180  | 70     | 52/100      |
| Mar  | 800   | 280 | 320  | 150  | 50     | 61/100      |

**Tendance :** +26 pts en 3 mois = Excellente progression !

---

## 🆘 Résolution de Problèmes

### Problème : Export Excel ne fonctionne pas

**Erreur :** Bouton "Excel (openpyxl requis)" désactivé

**Solution :**
```bash
pip install openpyxl
```

---

### Problème : Scores très bas (<30 en moyenne)

**Diagnostic :**
1. Analytics → Taux de complétude
2. Identifier les champs manquants

**Solutions :**
- SIREN manquant → Enrichir SIRENE
- Dirigeant/Téléphone manquant → Enrichir Pappers
- Email manquant → Impossible d'enrichir, contacts à nettoyer

---

### Problème : Pappers coûte trop cher

**Solution : Approche sélective**

1. Ne PAS enrichir tous les contacts
2. Workflow Auto → "Avec SIREN mais sans dirigeant"
3. Filtrer par score ≥ 50 (Warm uniquement)
4. Résultat : -70% de crédits Pappers consommés

**Exemple :**
- 500 contacts sans dirigeant
- Dont 200 Warm (score ≥ 50)
- Enrichir uniquement ces 200 → 200 crédits au lieu de 500

---

### Problème : UUIDs au lieu de noms d'entreprise

**Symptôme :** Contacts HubSpot affichent `aa148d1b-...`

**Cause :** Scope `companies.read` manquant dans votre Private App HubSpot

**Solution :**
1. HubSpot → Settings → Private Apps
2. Modifier votre app
3. Ajouter scope : `crm.objects.companies.read`
4. Sauvegarder
5. Re-synchroniser vos contacts

---

## 📞 Support

Pour toute question ou problème :

1. Consultez `VERIFICATION_TECHNIQUE.md` pour les détails techniques
2. Exécutez `python3 test_integration.py` pour vérifier votre installation
3. Vérifiez les logs Streamlit pour les erreurs

---

**Version :** 1.0
**Date :** 2025-11-23
**Auteur :** Claude Code (Anthropic)
