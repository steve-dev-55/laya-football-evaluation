# v0.2.0-real-integration — SDK Laya réel intégré, checkpoint épinglé

**Date :** 2026-09-29
**Scope :** étape 4/5 du processus de publication — exécution réelle (phase d'intégration)
**Commit :** f84dce6 · CI verte (142 tests, lint propre)

---

## Ce que contient cette release

### 1. Validation d'infrastructure sur corpus réel (4a — commit edd04c1)

Le pipeline complet §16 a été exécuté sur le corpus figé StatsBomb Open Data
(2 401 matchs collectés sur 2 403 visés, 125 340 snapshots, 10 compétitions,
3 saisons) avec le client mock déterministe :

- fuite de snapshots : **0,0000** (seuil §11.4 : 5 %) ;
- strates manquantes : **0,0000** (seuil : 10 %) ;
- taux de réponses invalides : **0,0000** (seuil : 5 %) ;
- 5/5 hypothèses préenregistrées évaluées de bout en bout ;
- rapport final 17 sections : `reports/real/final_report.md`.

Ceci prouve que l'infrastructure d'évaluation (collecte → nettoyage →
snapshots → prédictions → baselines → évaluation) fonctionne sur les données
réelles avant l'exécution confirmatoire.

### 2. Intégration du SDK Laya réel (4b — commit f84dce6)

`RealLayaClient` (`agents/laya.py`) branche le système sous test réel :

- **checkpoint épinglé et hashé** (exigence préenregistrée §2.1) :
  `laya` 0.3.21 (PyPI) · `convaiinnovations/laya-multilingual` @ `e4e9ddf2`
  · `model.safetensors` sha256 `9d628fd9…f204`, **vérifié au chargement** ;
- mapping figé des questions v1 (instructions verbatim, libellés neutres) ;
- réponse brute au contrat §9.1, **aucune renormalisation** (§8.6) ;
- import paresseux : la CI tourne sans laya/torch (142 tests verts).

### 3. Écarts d'exécution documentés (transparence post-enregistrement)

`docs/amendments/A3_execution_notes.md` documente trois écarts
d'infrastructure, sans toucher au plan scientifique :

| Écart | Contenu | Impact scientifique |
|---|---|---|
| **D1** | Tolérance de somme 2×10⁻³ (le SDK publie des probabilités arrondies à 4 décimales) | aucune renormalisation ; dérive ≤ 1,1×10⁻³ « MDE 9×10⁻³ |
| **D2** | `max_len` : 8192 (confirmatoire, maximum du checkpoint) / 2048 (pilot, contrainte CPU) | propriété déclarée du système sous test (§2.1) |
| **D3** | Pilot échantillonné (147 snapshots stratifiés) — contrainte de calcul | aucune conclusion confirmatoire tirée du pilot |

### 4. Pilot d'intégration exécuté sur états réels

`run_sdk_pilot_001` (147 snapshots stratifiés cutoff × tier + audit de
répétition k=5 sur ≥ 10 %) :

- **validité des réponses : 147/147 (0,0000 d'invalidité)** — le format du
  SDK passe le validateur §8.6 avec la tolérance D1 ;
- **déterminisme : sorties strictement identiques** sur les k=5 répétitions
  (JS max = 0, changement de décision = 0) — §9.2 validé ;
- latences réelles mesurées (p50/p95/max) : voir
  `reports/real/pilot_sdk_summary.md`.

*(Les chiffres ci-dessus sont mis à jour à la finalisation du pilot.)*

### 5. Run confirmatoire — prêt à exécuter

```bash
python -m pip install laya
python -m agents.laya      --run-id run_sdk_001 --config configs/experiment_real_sdk.yaml
python -m agents.baselines  --run-id run_sdk_001 --config configs/experiment_real_sdk.yaml
python -m agents.evaluator  --run-id run_sdk_001 --config configs/experiment_real_sdk.yaml
python -m agents.analyst    --run-id run_sdk_001 --config configs/experiment_real_sdk.yaml
```

**Pré-requis matériel** (mesuré, cf. A3 §8) : ~6 Go RAM libres en CPU fp32 à
`max_len=8192`, ou GPU (T4 recommandé : durée estimée 1-3 h pour ~94 000
requêtes vs ~500 h sur le CPU 2 cœurs du dépôt de développement).

---

## Prochaines étapes

1. Exécuter le run confirmatoire complet sur matériel adapté →
   `v1.0.0-results` ;
2. compléter le preprint (résultats) + arXiv (stat.AP/cs.LG) ;
3. diffusion (étape 5/5 : posts X/LinkedIn préparés dans `docs/diffusion/`).

## Ancre d'intégrité

- SHA-256 du protocole : `d8a3c83b…f4e8ea` (inchangé) ;
- pré-enregistrement OSF : [10.17605/OSF.IO/TPSQB](https://doi.org/10.17605/OSF.IO/TPSQB) ;
- état enregistré : commit `172b8d6` ; cette release : `f84dce6`.
