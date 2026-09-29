# Pilot SDK réel — synthèse d'intégration (A3/D3)

- **Run :** `run_sdk_pilot_001` — checkpoint `laya-multilingual` @ e4e9ddf21a7b1903b7acffd8814ad4307bf63a67
- **Prédictions :** 147 valides / 0 invalides (taux 0.0000, seuil §11.4 = 0,05)
- **Latence réelle :** p50 = 20622 ms, p95 = 21467 ms, max = 36669 ms (moyenne 20875 ms)
- **Audit de répétition (§9.2) :** k = 5 sur 15 snapshots — **toutes les sorties identiques** ✓
  (JS max = 0.0, changements de décision = 0.0)

## Latence moyenne par cutoff

| Cutoff (s) | n | latence moyenne (ms) |
|---|---|---|
| 0 | 21 | 22128 |
| 900 | 21 | 20905 |
| 1800 | 21 | 20888 |
| 2700 | 21 | 20524 |
| 3600 | 21 | 21023 |
| 4500 | 21 | 20423 |
| 5100 | 21 | 20232 |

Ce pilot n'est **pas** confirmatoire (échantillon stratifié, A3/D3). Le run confirmatoire complet (`configs/experiment_real_sdk.yaml`) doit être exécuté sur matériel adapté (GPU recommandé).
