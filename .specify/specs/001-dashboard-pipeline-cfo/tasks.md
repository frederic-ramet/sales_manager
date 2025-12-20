# Tasks - Module Dashboard Pipeline CFO

## Phase 1 : MVP Dashboard CFO

### T1.1 - Setup projet
**Durée** : 1h  
**Priorité** : 🔴 Bloquant

- [ ] Créer structure de dossiers (`core/`, `tests/`, `.specify/`)
- [ ] Créer `requirements.txt` avec dépendances
- [ ] Setup `.env.example` et `.gitignore`
- [ ] Créer les custom fields dans Asana (manuellement)
- [ ] Récupérer les GIDs des custom fields
- [ ] Setup Service Account Google et partager le Sheet

**Fichiers** : Structure projet  
**Dépend de** : Rien

---

### T1.2 - Client Asana
**Durée** : 3h  
**Priorité** : 🟠 Haute

- [ ] Créer `core/asana_client.py`
- [ ] Implémenter authentification PAT
- [ ] Implémenter `get_project_tasks()` avec opt_fields complets
- [ ] Implémenter `get_custom_field_gids()` pour validation
- [ ] Tester avec le vrai projet Asana
- [ ] Gérer rate limits et retry
- [ ] Tests unitaires basiques

**Fichiers** : `core/asana_client.py`, `tests/test_asana_client.py`  
**Dépend de** : T1.1

---

### T1.3 - Logique Pipeline & Calculs
**Durée** : 4h  
**Priorité** : 🟠 Haute

- [ ] Créer `core/pipeline.py`
- [ ] Implémenter `parse_tasks_to_dataframe()`
- [ ] Implémenter `calculate_metrics()` :
  - Probabilité basée sur confidence score
  - Revenue pondéré
  - Marge %
  - Dimensions temporelles (année, trimestre, mois)
  - Flags scénarios (conservateur, probable)
- [ ] Helper `_parse_custom_fields()` robuste
- [ ] Tests unitaires avec données mockées

**Fichiers** : `core/pipeline.py`, `tests/test_pipeline.py`  
**Dépend de** : T1.2

---

### T1.4 - Sync Google Sheets
**Durée** : 3h  
**Priorité** : 🟠 Haute

- [ ] Créer `core/sheets_sync.py`
- [ ] Implémenter `sync_pipeline()` avec création des 4 onglets :
  - Pipeline complet
  - Scénario conservateur
  - Scénario probable
  - Config/logs
- [ ] Implémenter `_write_to_sheet()` (clear + write)
- [ ] Gestion des erreurs (sheet not found, permissions)
- [ ] Tests unitaires (mock gspread)

**Fichiers** : `core/sheets_sync.py`, `tests/test_sheets_sync.py`  
**Dépend de** : T1.3

---

### T1.5 - Interface Streamlit
**Durée** : 3h  
**Priorité** : 🟡 Moyenne

- [ ] Créer `app.py`
- [ ] Page de configuration (sidebar) :
  - Input Asana PAT et Project GID
  - Input Google Sheet URL
  - Bouton "Test Asana" avec feedback
- [ ] Bouton "Sync maintenant" :
  - Loading state
  - Affichage nb deals récupérés
  - Preview du DataFrame
  - Messages de succès/erreur clairs
- [ ] Affichage dernière sync (timestamp)

**Fichiers** : `app.py`  
**Dépend de** : T1.4

---

### T1.6 - Tests d'intégration
**Durée** : 2h  
**Priorité** : 🟡 Moyenne

- [ ] Test end-to-end avec vrai projet Asana (3-5 deals)
- [ ] Vérifier que tous les custom fields sont récupérés
- [ ] Vérifier les calculs (probabilité, revenue pondéré, etc.)
- [ ] Vérifier la structure du Google Sheet généré
- [ ] Tester avec des deals sans certains champs (robustesse)
- [ ] Documentation des edge cases trouvés

**Fichiers** : `tests/test_integration.py`, notes dans README  
**Dépend de** : T1.5

---

### T1.7 - Documentation
**Durée** : 1h  
**Priorité** : 🟢 Basse

- [ ] README.md :
  - Installation (`pip install -r requirements.txt`)
  - Configuration (copie `.env.example` → `.env`)
  - Setup Asana (créer PAT, récupérer Project GID)
  - Setup Google Sheets (Service Account, partage)
  - Utilisation (`streamlit run app.py`)
- [ ] Documenter mapping custom fields attendus
- [ ] Troubleshooting commun

**Fichiers** : `README.md`  
**Dépend de** : T1.6

---

## ✅ Checkpoint Phase 1

**Critères de succès** :
- [ ] Sync manuelle fonctionne via interface Streamlit
- [ ] Les 4 onglets sont créés dans Google Sheets
- [ ] Calculs financiers corrects (vérifiés manuellement)
- [ ] Gestion d'erreurs (mauvais token, sheet inexistant, etc.)
- [ ] Documentation claire pour un nouvel utilisateur

**Livrable** : Application fonctionnelle déployable localement

---

## Phase 2 : Automatisation & Monitoring (Futur)

### T2.1 - Sync automatique
- [ ] Script cron ou scheduler Python
- [ ] Logs structurés (fichier + optionnel Streamlit)
- [ ] Alertes en cas d'échec (email ou Slack)

### T2.2 - Amélioration UX
- [ ] Historique des syncs (table SQLite)
- [ ] Graphiques Streamlit (CA par trimestre, etc.)
- [ ] Filtres interactifs dans l'UI

---

## Temps Total Estimé Phase 1

| Task | Durée |
|------|-------|
| T1.1 - Setup | 1h |
| T1.2 - Asana client | 3h |
| T1.3 - Pipeline & calculs | 4h |
| T1.4 - Sync Sheets | 3h |
| T1.5 - UI Streamlit | 3h |
| T1.6 - Tests intégration | 2h |
| T1.7 - Documentation | 1h |
| **TOTAL** | **17h** |

---

## Notes pour le Dev

1. **Commencer par T1.1** (setup) pour valider l'accès aux APIs
2. **T1.2 et T1.3** sont critiques - prendre le temps de bien les faire
3. **Tester incrémentalement** : ne pas attendre T1.6 pour tester
4. **Custom fields** : les créer AVANT T1.2, sinon blocage
5. **Service Account Google** : peut prendre 10-15min à setup correctement
