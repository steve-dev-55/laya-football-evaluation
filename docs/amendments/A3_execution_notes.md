# Amendement A3 — Notes d'exécution du run SDK réel (post-enregistrement)

**Statut :** document d'exécution (transparence §18, écart divulgé post-hoc)
**Date :** 2026-09-29
**Références :** protocole v2.0.0 §2.1, §8.6, §9.1, §9.2, §16 ; manifeste préenregistré (OSF tpsqb) ; amendements A1 (corpus réel, paires uniques) et A2 (découpage chronologique par compétition), tous deux antérieurs à l'enregistrement.

---

## 1. Objet

Cet amendement documente les adaptations d'**exécution** (infrastructure) nécessaires au branchement du SDK Laya réel sur le corpus figé. Aucune modification du plan scientifique (hypothèses §1.3, snapshots §5-§6, baselines §10, découpage §11, métriques §12, seuils de blocage §11.4) n'est introduite. Chaque écart est numéroté (D1, D2, D3) et sera reporté dans le rapport final (§18, divulgation).

## 2. Système sous test (§2.1) — épinglage vérifié

| Élément | Valeur |
|---|---|
| Paquet | `laya` 0.3.21 (PyPI) |
| Checkpoint | `convaiinnovations/laya-multilingual` |
| Commit Hugging Face | `e4e9ddf21a7b1903b7acffd8814ad4307bf63a67` (2026-09-24) |
| SHA-256 `model.safetensors` | `9d628fd971b700382ac6f65920a86f149777b2e748e0c955fb3b19695aa8f204` (vérifié au chargement par `expected_sha256`) |
| SHA-256 `tokenizer/tokenizer.json` | `609d8f4c067cd3950f88594c5a802616cea245823836ef5848ee4fc40aab5b6f` |
| Variante | `laya-multilingual` (mmBERT-base, 322 M paramètres, 22 couches, RoPE max 8192 positions) |
| Routeur | agent direct, `model="multilingual"` explicite — aucune reroute par détection de langue |
| Températures de calibration | `[1.0, 1.0, 1.0]` (config du checkpoint, déterministes) |
| Dépendances vérifiées | `torch` 2.14.0+cpu, `transformers` ≥ 4.48, `safetensors`, `numpy` — versions effectives consignées dans chaque artefact `laya_run.json` |

Le protocole exigeait (décision préenregistrée « laya_checkpoint ») que le checkpoint réel soit figé et hashé avant le run : c'est fait, le client refuse toute version `laya` installée différente de la version épinglée.

## 3. Mapping des questions (§8.5, wording figé)

Les questions v1 sont transmises au SDK avec les instructions **verbatim** :

- `score_bucket` → question `choice` ; chaque catégorie (16 scores exacts + `other`) devient une option au libellé seul (`criteria = {libellé: None}`), sans texte supplémentaire qui pourrait orienter la réponse ;
- `total_corners` → question `score` ; la liste ordonnée des 22 niveaux est passée telle quelle ;
- `total_yellow_cards` → question `score` ; liste ordonnée des 14 niveaux.

Le SDK retourne les probabilités indicées par position pour les questions `score` ; le client les traduit par `indice → criteria[i]` (règle figée, testée unitairement). Aucune probabilité reçue n'est modifiée.

## 4. Écart D1 — Tolérance de somme (arrondi 4 décimales du SDK)

**Constat mesuré.** Le SDK publie les distributions arrondies à 4 décimales (`round(p, 4)` dans `_decode_answers`). Pour 17 à 22 catégories, la somme d'une réponse peut dévier de 1 jusqu'à ≈ 1,1 × 10⁻³ (dérive observée : 0,9996 sur l'uniforme à 17 catégories). Le validateur §8.6 exigeait |somme − 1| ≤ 10⁻⁶.

**Décision.** Le run SDK utilise `sum_tolerance = 2 × 10⁻³` (marge ≥ 1,8 × la dérive maximale théorique). Les probabilités sont stockées et évaluées **telles que reçues** : aucune renormalisation (§8.6 interdit), le plancher ε = 10⁻¹⁵ du log loss (§12.1, préenregistré) couvre les probabilités arrondies à 0. Les runs mock et les tests conservent la tolérance 10⁻⁶ par défaut.

**Justification scientifique.** L'arrondi est une propriété du format de sortie du système sous test tel que déployé ; le rejeter comme « réponse invalide » écarterait 100 % des réponses réelles pour un artefact de sérialisation. La dérive (≤ 1,1 × 10⁻³) est inférieure d'un ordre de grandeur aux MDE visés (≥ 9 × 10⁻³ log loss).

## 5. Écart D2 — Budget de contexte et troncature tokenizer

**Constat mesuré.** Le JSON canonique se tokenise à ≈ 1,56 caractère/jeton (11 866 caractères → 7 615 jetons ; les identifiants hexadécimaux de provenance sont très coûteux en jetons). À `max_len = 8192` (maximum du checkpoint), ≈ 12 800 caractères sont lisibles ; à `max_len = 2048`, ≈ 3 200 caractères.

**Structure de l'état (clés triées) :** `live` (≤ ~6 ko, dont agrégats de score en tête après la liste d'événements) précède `metadata` (inclut `pre_match_source_match_ids`, jusqu'à ~100 ko d'identifiants d'audit) puis `pre_match` (~0,4 ko de features). La troncature du tokenizer conserve le préfixe : la section `live` reste visible dans tous les cas à 8192 ; les features `pre_match` sont tronquées pour les états dont les identifiants de provenance consomment le budget.

**Décision.**
- Run confirmatoire (`configs/experiment_real_sdk.yaml`) : `max_len = 8192`, le maximum du checkpoint — meilleure restitution de l'état par le système.
- Pilot CPU (`configs/experiment_pilot_sdk.yaml`) : `max_len = 2048` — limite mémoire mesurée de la machine d'exécution (pic 3,15 Go / 4 Go à 2048 ; OOM à 4096 et 8192).
- La politique de troncature est celle du tokenizer du SDK (préfixe conservé), appliquée à la sérialisation canonique hash-épinglée §9.1 : aucun remaniement côté client.

## 6. Écart D3 — Pilot échantillonné et contrainte de calcul

**Constat mesuré.** La machine d'exécution (2 cœurs CPU, 4 Go cgroup, sans GPU) délivre ≈ 19,3 s par prédiction à `max_len = 2048` (fp32, 3 questions par état, ~6 144 jetons-lignes). Le run confirmatoire complet (62 670 snapshots de test §11.1/A2 + audit de répétition ≈ 31 335 requêtes) représenterait ≈ 500 à 1 000 heures-core : infaisable localement.

**Décision.**
1. Un **pilot d'intégration** (`run_sdk_pilot_001`) est exécuté localement : 147 snapshots (7 par strate (cutoff fixe × tier)), audit de répétition k = 5 sur ≥ 10 % du périmètre. Il produit les preuves d'intégration (validité des réponses, latence réelle, déterminisme) — **aucune conclusion confirmatoire n'en est tirée**.
2. Le **run confirmatoire complet** s'exécute sur matériel adapté (GPU T4 recommandé — le SDK documente 33 ms/question ; temps estimé 1 à 3 h pour ~94 000 requêtes batchées) via `configs/experiment_real_sdk.yaml`, inchangé par rapport au plan enregistré.

**Règle d'échantillonnage du pilot (déterministe, auditable).** Strates = produit croisé (cutoff fixe × tier), sélection au pas régulier dans les snapshot_ids triés, liste complète conservée dans `data/real/artifacts/run_sdk_pilot_001/sampling_selection.json`.

## 7. Déterminisme (§9.2)

Vérifié à deux niveaux : (i) smoke test — deux appels identiques retournent des réponses strictement identiques (hash égal) ; (ii) audit de répétition k = 5 du pilot. Les températures de calibration du checkpoint sont fixes ; le mode évaluation du modèle est déterministe.

## 8. Plan du run confirmatoire complet

```bash
# Pré-requis : ~6 Go RAM libres (CPU fp32) ou GPU (recommandé : T4, Kaggle/Colab)
python -m pip install laya                                  # PyPI 0.3.21
python -m agents.laya --run-id run_sdk_001 \
    --config configs/experiment_real_sdk.yaml               # ~94 000 requêtes
python -m agents.baselines --run-id run_sdk_001 \
    --config configs/experiment_real_sdk.yaml
python -m agents.evaluator --run-id run_sdk_001 \
    --config configs/experiment_real_sdk.yaml
python -m agents.analyst --run-id run_sdk_001 \
    --config configs/experiment_real_sdk.yaml
```

Ordre inchangé (§16) ; la chaîne de hash d'artefacts §15 s'applique comme au run mock. Estimations mesurées :

| Matériel | Latence/prédiction (2048) | Durée estimée (94k req.) |
|---|---|---|
| 2 cœurs CPU (ce dépôt) | ~19,3 s | ~500 h — infaisable |
| 8 cœurs CPU (estimé) | ~5-8 s | ~130-210 h |
| GPU T4 (batch, documenté SDK) | ~20-100 ms | ~1-3 h |

## 9. Impact sur les seuils de blocage (§11.4)

Aucun. Les trois seuils (fuite 5 %, strates manquantes 10 %, réponses invalides 5 %) s'appliquent au run confirmatoire avec les définitions enregistrées. La tolérance D1 ne modifie pas le taux d'invalidité (elle le rend mesurable), et la troncature D2 est une propriété déclarée du système sous test (§2.1 « longueur maximale de contexte »), pas une exclusion de snapshots.
