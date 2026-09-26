# Rapport final — Évaluation de Laya (protocole v2.0.0)

- **Expérience :** laya-football-001 — run `local_smoke_run`
- **Généré le :** 2026-09-26T09:20:35Z (UTC)
- **Structure :** §20 du protocole (17 sections numérotées)

> Avertissement (§0.2, §18) : ce rapport est un document scientifique pré-enregistré ; il ne constitue ni un conseil de pari ni une garantie de résultat. Les sections sans donnée affichent « en attente d'exécution ».

## 1. Résumé exécutif


- **Expérience :** laya-football-001 — run `local_smoke_run` (protocole v2.0.0).
- **Statut du pipeline :** collector_coverage = validated; cleaning_report = validated; pre_match_validation = validated; snapshot_validation = validated; laya_run = validated; repetition_audit = validated; baselines_run = validated ; evaluation_report = validated.
- **Périmètre analysé :** 120 matchs inclus (sur 120 collectés), 4569 snapshots, 4569 prédictions Laya valides (taux d'invalidité 0.0000).
- **Contrôles bloquants §11.4 :** invalid_response_rate = 0.0000 (seuil 0.0500) → passé ; snapshot_leakage_rate = 0.0000 (seuil 0.0500) → passé ; stratum_missing_rate = 0.0000 (seuil 0.1000) → passé.
- **Hypothèses pré-enregistrées évaluées :** 5 sur 5 (détail en section 13).
- **AVERTISSEMENT — mode démonstration :** le client Laya est un client *mock* déterministe et les données sont synthétiques ; AUCUNE conclusion sur le système Laya réel ne peut être tirée de ce run (§0.3).

## 2. Questions et hypothèses pré-enregistrées


Question principale (§1.1) : à information disponible à la minute `t`, Laya produit-il des distributions prédictives mieux calibrées et/ou plus discriminantes que les baselines pour le 1X2, le score regroupé, les corners et les cartons jaunes ?

Hypothèses confirmatoires pré-enregistrées (§1.3) :
- **H1_progression_temporelle** — la log loss 1X2 diminue lorsque le cutoff passe de pré-match à 85 minutes
- **H2_calibration** — la calibration de Laya, mesurée par ECE et log loss, est meilleure que celle de la baseline historique à information identique
- **H3_reaction_apres_but** — après un but, la probabilité du vainqueur correspondant augmente en moyenne, toutes choses égales par ailleurs
- **H4_robustesse** — les paraphrases sémantiquement équivalentes ne modifient pas fortement la distribution prédictive
- **H5_comptages** — pour corners et cartons, la performance de Laya est comparée séparément à une baseline moyenne historique et à un modèle de comptage adapté

Une hypothèse non écrite dans le manifeste avant l'évaluation du test final est exploratoire et ne doit jamais être présentée comme confirmatoire (§1.3).

## 3. Sources, périmètre et exclusions


- **Source principale :** LOCAL_FILE (à remplacer : StatsBomb/API-Football/FBref à figer avant collecte)
- **Source secondaire :** à figer avant la collecte
- **Compétitions :** EPL, LaLiga, SerieA, Bundesliga, Ligue1 ; **saisons :** 2021-2022, 2022-2023, 2023-2024.
- **Couverture du collecteur :** 15/15 documents.
- **Exclusions motivées (§3.4) :** 0 match(s) exclu(s).

- **Taux de matchs manquants maximal par strate :** 0.0000 (seuil 0.1000).

## 4. Définition point-in-time et contrôles anti-fuite


- Référence temporelle : UTC ISO-8601 ; cutoffs fixes = 0 s, 900 s, 1800 s, 2700 s, 3600 s, 4500 s, 5100 s (§5.1, §6.1) + snapshots événementiels (§6.2).
- Tiers d'information : A, B, C (décision annexe B ; définitions §6.3).
- Tests anti-fuite exécutés sur 100 % des snapshots (§5.5) : test_no_future_events (§5.5) ; test_no_final_fields (§5.5) ; test_pre_match_sources_before_cutoff (§5.5) ; cohérence cutoff/événements embarqués (§5.3).
- Résultat : 0 snapshot(s) bloqué(s) sur 4569 ; taux de fuite = 0.0000 (seuil §11.4 : 5 %).
- Contexte pré-match : 240 contextes pour 120 matchs ; 0 bloqué(s) ; 1 sans historique (features null, §7.2).

## 5. Version de Laya et tâches typées


- **Paquet :** laya-mock.
- **Version :** 1.0.0.
- **Checkpoint :** PINNED_CHECKPOINT.
- **Mode routeur :** multilingual ; contexte maximal : 200000 caractères.
- **Version des questions :** v1 (QUESTIONS_V1 : score_bucket 17 catégories, total_corners 22 niveaux dont 21+, total_yellow_cards 14 niveaux dont 13+, §8.5).
- Dérivations pré-enregistrées : 1X2 dérivé de la distribution de score regroupé (§8.1) ; espérances censurées aux seuils de queue (§8.3, §8.4) ; aucune renormalisation d'une réponse reçue (§8.6).
- **Réponses :** 4569 valides / 4569 snapshots ; taux d'invalidité = 0.0000 (seuil 0.0500).

## 6. Baselines et découpage temporel


- Baselines (§10.1, §10.2) : `current_score` (4569), `historical_frequency` (4569), `logistic_1x2` (1503), `persistence` (4569), `poisson` (4569), `uniform` (4569).
- Comparaison équitable (§10.4) : mêmes snapshots, mêmes cutoffs, mêmes informations que Laya.
- Découpage temporel (§11.1) : entraînement = 2021-2022, 2022-2023 (80 matchs, kickoffs 2021-08-14T13:00:00Z → 2022-08-27T21:00:00Z) ; test final = saisons les plus récentes. Aucun entraînement sur le test final.

## 7. Métriques et plan statistique


- **Métriques principales par cible (annexe B) :** 1x2 = log_loss ; score_bucket = log_loss ; corners = crps ; yellow_cards = crps.
- Métriques secondaires : Brier, RPS, exactitude, MAE censurées, masse de queue, PIT randomisé, couverture 50/80/95 % (§12.3, §12.4).
- **Bootstrap :** bootstrap stratifié et groupé par match (§11.2, §12.5) ; 2000 réplications ; alpha = 0.05 ; seed = 20260925 (§12.5).
- Corrections multiples : Holm-Bonferroni, une famille par cible (4 familles, décision annexe B) ; un test non significatif ne prouve pas l'égalité des modèles (§12.5).

## 8. Résultats globaux


Scope : saison(s) test (split temporel §11.1). Chaque ligne reprend l'agrégat fourni par l'évaluateur, sans recalcul.

| Modèle | Cible | Métrique | Cutoff | Matchs | Snapshots | Réponses valides | Valeur [IC 95 %] |
|---|---|---|---|---|---|---|---|
| current_score | 1x2 | log loss 1X2 | tous (0–5100 s) | 40 | 1503 | 15.0161 [12.4142 ; 17.4837] |
| current_score | score_bucket | log loss score regroupé | tous (0–5100 s) | 40 | 1503 | 22.6996 [19.3976 ; 25.6103] |
| current_score | corners | CRPS corners | tous (0–5100 s) | 40 | 1503 | 9.9666 [8.7842 ; 11.1385] |
| current_score | yellow_cards | CRPS cartons jaunes | tous (0–5100 s) | 40 | 1503 | 3.2708 [2.9748 ; 3.5547] |
| historical_frequency | 1x2 | log loss 1X2 | tous (0–5100 s) | 40 | 1503 | 1.2805 [1.2261 ; 1.3347] |
| historical_frequency | score_bucket | log loss score regroupé | tous (0–5100 s) | 40 | 1503 | 12.9535 [8.1833 ; 17.7330] |
| historical_frequency | corners | CRPS corners | tous (0–5100 s) | 40 | 1503 | 3.2946 [2.7874 ; 3.8174] |
| historical_frequency | yellow_cards | CRPS cartons jaunes | tous (0–5100 s) | 40 | 1503 | 0.8466 [0.6987 ; 1.0084] |
| laya | 1x2 | log loss 1X2 | tous (0–5100 s) | 40 | 1503 | 1.2795 [0.8852 ; 1.7502] |
| laya | score_bucket | log loss score regroupé | tous (0–5100 s) | 40 | 1503 | 2.1297 [1.9097 ; 2.3485] |
| laya | corners | CRPS corners | tous (0–5100 s) | 40 | 1503 | 4.5987 [3.6694 ; 5.5373] |
| laya | yellow_cards | CRPS cartons jaunes | tous (0–5100 s) | 40 | 1503 | 1.3928 [1.2031 ; 1.5837] |
| logistic_1x2 | 1x2 | log loss 1X2 | tous (0–5100 s) | 40 | 1503 | 0.6652 [0.3709 ; 0.9998] |
| logistic_1x2 | score_bucket | log loss score regroupé | tous (0–5100 s) | 40 | 1503 | en attente d'exécution |
| logistic_1x2 | corners | CRPS corners | tous (0–5100 s) | 40 | 1503 | en attente d'exécution |
| logistic_1x2 | yellow_cards | CRPS cartons jaunes | tous (0–5100 s) | 40 | 1503 | en attente d'exécution |
| persistence | 1x2 | log loss 1X2 | tous (0–5100 s) | 40 | 1503 | 1.4150 [1.0442 ; 1.8746] |
| persistence | score_bucket | log loss score regroupé | tous (0–5100 s) | 40 | 1503 | 2.3399 [2.0929 ; 2.5780] |
| persistence | corners | CRPS corners | tous (0–5100 s) | 40 | 1503 | 3.8756 [3.1578 ; 4.6313] |
| persistence | yellow_cards | CRPS cartons jaunes | tous (0–5100 s) | 40 | 1503 | 1.3261 [1.1462 ; 1.5065] |
| poisson | 1x2 | log loss 1X2 | tous (0–5100 s) | 40 | 1503 | 1.2725 [0.8808 ; 1.7466] |
| poisson | score_bucket | log loss score regroupé | tous (0–5100 s) | 40 | 1503 | 2.1305 [1.9023 ; 2.3537] |
| poisson | corners | CRPS corners | tous (0–5100 s) | 40 | 1503 | 3.8756 [3.1578 ; 4.6313] |
| poisson | yellow_cards | CRPS cartons jaunes | tous (0–5100 s) | 40 | 1503 | 1.3261 [1.1462 ; 1.5065] |
| uniform | 1x2 | log loss 1X2 | tous (0–5100 s) | 40 | 1503 | 1.1529 [1.1023 ; 1.2138] |
| uniform | score_bucket | log loss score regroupé | tous (0–5100 s) | 40 | 1503 | 2.8332 [2.8332 ; 2.8332] |
| uniform | corners | CRPS corners | tous (0–5100 s) | 40 | 1503 | 3.4728 [2.9318 ; 4.0750] |
| uniform | yellow_cards | CRPS cartons jaunes | tous (0–5100 s) | 40 | 1503 | 1.7321 [1.5964 ; 1.8821] |

Méthode de bootstrap : bootstrap stratifié et groupé par match (§11.2, §12.5) (2000 réplications).

Dénominateurs et taux d'invalidité (§19.2.5) :
| Modèle | Prédictions | Prédictions (scope test) | Matchs | Taux d'invalidité |
|---|---|---|---|---|
| current_score | 4569 | 1503 | 120 | 0.0000 |
| historical_frequency | 4569 | 1503 | 120 | 0.0000 |
| laya | 4569 | 1503 | 120 | 0.0000 |
| logistic_1x2 | 1503 | 1503 | 40 | 0.0000 |
| persistence | 4569 | 1503 | 120 | 0.0000 |
| poisson | 4569 | 1503 | 120 | 0.0000 |
| uniform | 4569 | 1503 | 120 | 0.0000 |
| laya (total toutes saisons) | 4569 | — | — | 0.0000 |

## 9. Résultats par cutoff, compétition et tier


**Par cutoff (scope test, log loss 1X2 moyen) :**

| Cutoff | Modèle | Prédictions | Log loss 1X2 (moyenne) |
|---|---|---|---|
| 0 s | current_score | 120 | 25.0406 |
| 0 s | historical_frequency | 120 | 1.2805 |
| 0 s | laya | 120 | 0.9653 |
| 0 s | logistic_1x2 | 120 | 0.6652 |
| 0 s | persistence | 120 | 1.2074 |
| 0 s | poisson | 120 | 0.9444 |
| 0 s | uniform | 120 | 1.1529 |
| 289 s | current_score | 3 | 11.5129 |
| 289 s | historical_frequency | 3 | 1.5041 |
| 289 s | laya | 3 | 0.5518 |
| 289 s | logistic_1x2 | 3 | 0.8853 |
| 289 s | persistence | 3 | 1.1404 |
| 289 s | poisson | 3 | 0.5705 |
| 289 s | uniform | 3 | 1.0414 |
| 310 s | current_score | 3 | 11.5129 |
| 310 s | historical_frequency | 3 | 1.4816 |
| 310 s | laya | 3 | 0.7464 |
| 310 s | logistic_1x2 | 3 | 0.2209 |
| 310 s | persistence | 3 | 0.9602 |
| 310 s | poisson | 3 | 0.7551 |
| 310 s | uniform | 3 | 1.0414 |
| 350 s | current_score | 3 | 11.5129 |
| 350 s | historical_frequency | 3 | 1.2528 |
| 350 s | laya | 3 | 0.4081 |
| 350 s | logistic_1x2 | 3 | 0.4913 |
| 350 s | persistence | 3 | 0.6238 |
| 350 s | poisson | 3 | 0.4448 |
| 350 s | uniform | 3 | 1.0414 |
| 419 s | current_score | 3 | 11.5129 |
| 419 s | historical_frequency | 3 | 1.4816 |
| 419 s | laya | 3 | 1.1107 |
| 419 s | logistic_1x2 | 3 | 0.2209 |
| 419 s | persistence | 3 | 0.8841 |
| 419 s | poisson | 3 | 1.1410 |
| 419 s | uniform | 3 | 1.0414 |
| 482 s | current_score | 3 | 34.5388 |
| 482 s | historical_frequency | 3 | 1.4816 |
| 482 s | laya | 3 | 0.5116 |
| 482 s | logistic_1x2 | 3 | 0.4568 |
| 482 s | persistence | 3 | 1.4836 |
| 482 s | poisson | 3 | 0.5523 |
| 482 s | uniform | 3 | 1.0414 |
| 497 s | current_score | 3 | 11.5129 |
| 497 s | historical_frequency | 3 | 1.2528 |
| 497 s | laya | 3 | 0.5106 |
| 497 s | logistic_1x2 | 3 | 0.3280 |
| 497 s | persistence | 3 | 0.5975 |
| 497 s | poisson | 3 | 0.5151 |
| 497 s | uniform | 3 | 1.0414 |
| 500 s | current_score | 3 | 23.0259 |
| 500 s | historical_frequency | 3 | 1.1527 |
| 500 s | laya | 3 | 1.8791 |
| 500 s | logistic_1x2 | 3 | 1.9442 |
| 500 s | persistence | 3 | 1.5753 |
| 500 s | poisson | 3 | 1.8750 |
| 500 s | uniform | 3 | 1.4469 |
| 525 s | current_score | 3 | 11.5129 |
| 525 s | historical_frequency | 3 | 1.1896 |
| 525 s | laya | 3 | 0.6880 |
| 525 s | logistic_1x2 | 3 | 0.0270 |
| 525 s | persistence | 3 | 0.7117 |
| 525 s | poisson | 3 | 0.7128 |
| 525 s | uniform | 3 | 1.0414 |
| 597 s | current_score | 3 | 11.5129 |
| 597 s | historical_frequency | 3 | 1.4816 |
| 597 s | laya | 3 | 0.4843 |
| 597 s | logistic_1x2 | 3 | 0.4568 |
| 597 s | persistence | 3 | 0.9670 |
| 597 s | poisson | 3 | 0.4760 |
| 597 s | uniform | 3 | 1.0414 |
| 613 s | current_score | 3 | 11.5129 |
| 613 s | historical_frequency | 3 | 1.2238 |
| 613 s | laya | 3 | 0.5269 |
| 613 s | logistic_1x2 | 3 | 0.1460 |
| 613 s | persistence | 3 | 0.5780 |
| 613 s | poisson | 3 | 0.5172 |
| 613 s | uniform | 3 | 1.0414 |
| 656 s | current_score | 3 | 23.0259 |
| 656 s | historical_frequency | 3 | 1.0498 |
| 656 s | laya | 3 | 1.2644 |
| 656 s | logistic_1x2 | 3 | 0.3790 |
| 656 s | persistence | 3 | 1.6060 |
| 656 s | poisson | 3 | 1.2553 |
| 656 s | uniform | 3 | 1.4469 |
| 741 s | current_score | 3 | 11.5129 |
| 741 s | historical_frequency | 3 | 1.1896 |
| 741 s | laya | 3 | 0.5582 |
| 741 s | logistic_1x2 | 3 | 0.0435 |
| 741 s | persistence | 3 | 0.5909 |
| 741 s | poisson | 3 | 0.5738 |
| 741 s | uniform | 3 | 1.0414 |
| 750 s | current_score | 3 | 0.0000 |
| 750 s | historical_frequency | 3 | 1.0498 |
| 750 s | laya | 3 | 1.0481 |
| 750 s | logistic_1x2 | 3 | 0.3790 |
| 750 s | persistence | 3 | 1.1827 |
| 750 s | poisson | 3 | 1.0103 |
| 750 s | uniform | 3 | 1.4469 |
| 753 s | current_score | 3 | 11.5129 |
| 753 s | historical_frequency | 3 | 1.1896 |
| 753 s | laya | 3 | 0.5175 |
| 753 s | logistic_1x2 | 3 | 0.0220 |
| 753 s | persistence | 3 | 0.5862 |
| 753 s | poisson | 3 | 0.5781 |
| 753 s | uniform | 3 | 1.0414 |
| 788 s | current_score | 3 | 11.5129 |
| 788 s | historical_frequency | 3 | 1.3437 |
| 788 s | laya | 3 | 0.7501 |
| 788 s | logistic_1x2 | 3 | 0.0222 |
| 788 s | persistence | 3 | 0.7341 |
| 788 s | poisson | 3 | 0.7816 |
| 788 s | uniform | 3 | 1.0414 |
| 791 s | current_score | 3 | 11.5129 |
| 791 s | historical_frequency | 3 | 1.5041 |
| 791 s | laya | 3 | 0.4634 |
| 791 s | logistic_1x2 | 3 | 0.8725 |
| 791 s | persistence | 3 | 0.9238 |
| 791 s | poisson | 3 | 0.4611 |
| 791 s | uniform | 3 | 1.0414 |
| 822 s | current_score | 3 | 23.0259 |
| 822 s | historical_frequency | 3 | 1.0498 |
| 822 s | laya | 3 | 1.5870 |
| 822 s | logistic_1x2 | 3 | 0.3790 |
| 822 s | persistence | 3 | 1.3122 |
| 822 s | poisson | 3 | 1.4841 |
| 822 s | uniform | 3 | 1.4469 |
| 840 s | current_score | 3 | 34.5388 |
| 840 s | historical_frequency | 3 | 1.2528 |
| 840 s | laya | 3 | 0.6261 |
| 840 s | logistic_1x2 | 3 | 0.1431 |
| 840 s | persistence | 3 | 0.9667 |
| 840 s | poisson | 3 | 0.6383 |
| 840 s | uniform | 3 | 1.0414 |
| 876 s | current_score | 3 | 11.5129 |
| 876 s | historical_frequency | 3 | 1.2993 |
| 876 s | laya | 3 | 0.6261 |
| 876 s | logistic_1x2 | 3 | 0.2351 |
| 876 s | persistence | 3 | 0.8715 |
| 876 s | poisson | 3 | 0.6776 |
| 876 s | uniform | 3 | 1.0414 |
| 900 s | current_score | 120 | 19.8598 |
| 900 s | historical_frequency | 120 | 1.2805 |
| 900 s | laya | 120 | 0.9176 |
| 900 s | logistic_1x2 | 120 | 0.6652 |
| 900 s | persistence | 120 | 1.0799 |
| 900 s | poisson | 120 | 0.8940 |
| 900 s | uniform | 120 | 1.1529 |
| 921 s | current_score | 3 | 23.0259 |
| 921 s | historical_frequency | 3 | 1.1632 |
| 921 s | laya | 3 | 1.6937 |
| 921 s | logistic_1x2 | 3 | 0.3988 |
| 921 s | persistence | 3 | 1.2708 |
| 921 s | poisson | 3 | 1.9664 |
| 921 s | uniform | 3 | 1.4469 |
| 931 s | current_score | 3 | 11.5129 |
| 931 s | historical_frequency | 3 | 1.5041 |
| 931 s | laya | 3 | 0.4176 |
| 931 s | logistic_1x2 | 3 | 0.6729 |
| 931 s | persistence | 3 | 0.9322 |
| 931 s | poisson | 3 | 0.4650 |
| 931 s | uniform | 3 | 1.0414 |
| 996 s | current_score | 3 | 23.0259 |
| 996 s | historical_frequency | 3 | 0.9808 |
| 996 s | laya | 3 | 1.4494 |
| 996 s | logistic_1x2 | 3 | 0.4325 |
| 996 s | persistence | 3 | 1.5664 |
| 996 s | poisson | 3 | 1.3652 |
| 996 s | uniform | 3 | 1.4469 |
| 1020 s | current_score | 3 | 34.5388 |
| 1020 s | historical_frequency | 3 | 1.5041 |
| 1020 s | laya | 3 | 0.6528 |
| 1020 s | logistic_1x2 | 3 | 0.8853 |
| 1020 s | persistence | 3 | 1.6810 |
| 1020 s | poisson | 3 | 0.7296 |
| 1020 s | uniform | 3 | 1.0414 |
| 1098 s | current_score | 3 | 34.5388 |
| 1098 s | historical_frequency | 3 | 1.5041 |
| 1098 s | laya | 3 | 0.6557 |
| 1098 s | logistic_1x2 | 3 | 0.6729 |
| 1098 s | persistence | 3 | 1.4667 |
| 1098 s | poisson | 3 | 0.7248 |
| 1098 s | uniform | 3 | 1.0414 |
| 1205 s | current_score | 3 | 11.5129 |
| 1205 s | historical_frequency | 3 | 1.1896 |
| 1205 s | laya | 3 | 0.7741 |
| 1205 s | logistic_1x2 | 3 | 0.0220 |
| 1205 s | persistence | 3 | 0.5505 |
| 1205 s | poisson | 3 | 0.8133 |
| 1205 s | uniform | 3 | 1.0414 |
| 1213 s | current_score | 3 | 11.5129 |
| 1213 s | historical_frequency | 3 | 1.0415 |
| 1213 s | laya | 3 | 0.4686 |
| 1213 s | logistic_1x2 | 3 | 0.1293 |
| 1213 s | persistence | 3 | 0.5952 |
| 1213 s | poisson | 3 | 0.4859 |
| 1213 s | uniform | 3 | 1.0414 |
| 1383 s | current_score | 3 | 11.5129 |
| 1383 s | historical_frequency | 3 | 1.3437 |
| 1383 s | laya | 3 | 0.8881 |
| 1383 s | logistic_1x2 | 3 | 0.0222 |
| 1383 s | persistence | 3 | 0.6809 |
| 1383 s | poisson | 3 | 0.9849 |
| 1383 s | uniform | 3 | 1.0414 |
| 1399 s | current_score | 3 | 11.5129 |
| 1399 s | historical_frequency | 3 | 1.3350 |
| 1399 s | laya | 3 | 1.4438 |
| 1399 s | logistic_1x2 | 3 | 5.1997 |
| 1399 s | persistence | 3 | 0.9621 |
| 1399 s | poisson | 3 | 1.2579 |
| 1399 s | uniform | 3 | 1.0414 |
| 1443 s | current_score | 3 | 34.5388 |
| 1443 s | historical_frequency | 3 | 1.7918 |
| 1443 s | laya | 3 | 0.4969 |
| 1443 s | logistic_1x2 | 3 | 0.7985 |
| 1443 s | persistence | 3 | 1.6103 |
| 1443 s | poisson | 3 | 0.5323 |
| 1443 s | uniform | 3 | 1.0414 |
| 1532 s | current_score | 3 | 11.5129 |
| 1532 s | historical_frequency | 3 | 1.3437 |
| 1532 s | laya | 3 | 1.6462 |
| 1532 s | logistic_1x2 | 3 | 0.0222 |
| 1532 s | persistence | 3 | 1.0736 |
| 1532 s | poisson | 3 | 1.7078 |
| 1532 s | uniform | 3 | 1.0414 |
| 1595 s | current_score | 3 | 11.5129 |
| 1595 s | historical_frequency | 3 | 1.5041 |
| 1595 s | laya | 3 | 0.5717 |
| 1595 s | logistic_1x2 | 3 | 0.8725 |
| 1595 s | persistence | 3 | 0.7371 |
| 1595 s | poisson | 3 | 0.5653 |
| 1595 s | uniform | 3 | 1.0414 |
| 1641 s | current_score | 3 | 23.0259 |
| 1641 s | historical_frequency | 3 | 1.1527 |
| 1641 s | laya | 3 | 2.5613 |
| 1641 s | logistic_1x2 | 3 | 1.9442 |
| 1641 s | persistence | 3 | 2.1859 |
| 1641 s | poisson | 3 | 2.5972 |
| 1641 s | uniform | 3 | 1.4469 |
| 1661 s | current_score | 3 | 0.0000 |
| 1661 s | historical_frequency | 3 | 1.1632 |
| 1661 s | laya | 3 | 1.0721 |
| 1661 s | logistic_1x2 | 3 | 0.3988 |
| 1661 s | persistence | 3 | 0.9448 |
| 1661 s | poisson | 3 | 0.9281 |
| 1661 s | uniform | 3 | 1.4469 |
| 1684 s | current_score | 3 | 11.5129 |
| 1684 s | historical_frequency | 3 | 1.2238 |
| 1684 s | laya | 3 | 0.5538 |
| 1684 s | logistic_1x2 | 3 | 0.1460 |
| 1684 s | persistence | 3 | 0.5415 |
| 1684 s | poisson | 3 | 0.5490 |
| 1684 s | uniform | 3 | 1.0414 |
| 1699 s | current_score | 3 | 34.5388 |
| 1699 s | historical_frequency | 3 | 1.2993 |
| 1699 s | laya | 3 | 0.4220 |
| 1699 s | logistic_1x2 | 3 | 0.1658 |
| 1699 s | persistence | 3 | 1.4578 |
| 1699 s | poisson | 3 | 0.4860 |
| 1699 s | uniform | 3 | 1.0414 |
| 1727 s | current_score | 3 | 11.5129 |
| 1727 s | historical_frequency | 3 | 1.1896 |
| 1727 s | laya | 3 | 0.6340 |
| 1727 s | logistic_1x2 | 3 | 0.0220 |
| 1727 s | persistence | 3 | 0.5219 |
| 1727 s | poisson | 3 | 0.6903 |
| 1727 s | uniform | 3 | 1.0414 |
| 1731 s | current_score | 3 | 11.5129 |
| 1731 s | historical_frequency | 3 | 1.3350 |
| 1731 s | laya | 3 | 0.4697 |
| 1731 s | logistic_1x2 | 3 | 0.3233 |
| 1731 s | persistence | 3 | 0.5982 |
| 1731 s | poisson | 3 | 0.4969 |
| 1731 s | uniform | 3 | 1.0414 |
| 1753 s | current_score | 3 | 11.5129 |
| 1753 s | historical_frequency | 3 | 1.1896 |
| 1753 s | laya | 3 | 0.4989 |
| 1753 s | logistic_1x2 | 3 | 0.0270 |
| 1753 s | persistence | 3 | 0.6252 |
| 1753 s | poisson | 3 | 0.4967 |
| 1753 s | uniform | 3 | 1.0414 |
| 1800 s | current_score | 120 | 18.7085 |
| 1800 s | historical_frequency | 120 | 1.2805 |
| 1800 s | laya | 120 | 0.8800 |
| 1800 s | logistic_1x2 | 120 | 0.6652 |
| 1800 s | persistence | 120 | 1.0487 |
| 1800 s | poisson | 120 | 0.8621 |
| 1800 s | uniform | 120 | 1.1529 |
| 1835 s | current_score | 3 | 11.5129 |
| 1835 s | historical_frequency | 3 | 1.0986 |
| 1835 s | laya | 3 | 0.4438 |
| 1835 s | logistic_1x2 | 3 | 0.1503 |
| 1835 s | persistence | 3 | 0.5851 |
| 1835 s | poisson | 3 | 0.4424 |
| 1835 s | uniform | 3 | 1.0414 |
| 1856 s | current_score | 3 | 11.5129 |
| 1856 s | historical_frequency | 3 | 1.2993 |
| 1856 s | laya | 3 | 0.7809 |
| 1856 s | logistic_1x2 | 3 | 0.2351 |
| 1856 s | persistence | 3 | 0.6897 |
| 1856 s | poisson | 3 | 0.7785 |
| 1856 s | uniform | 3 | 1.0414 |
| 1879 s | current_score | 3 | 11.5129 |
| 1879 s | historical_frequency | 3 | 1.1896 |
| 1879 s | laya | 3 | 0.6526 |
| 1879 s | logistic_1x2 | 3 | 0.0220 |
| 1879 s | persistence | 3 | 0.6914 |
| 1879 s | poisson | 3 | 0.7339 |
| 1879 s | uniform | 3 | 1.0414 |
| 1902 s | current_score | 3 | 0.0000 |
| 1902 s | historical_frequency | 3 | 0.9808 |
| 1902 s | laya | 3 | 1.3404 |
| 1902 s | logistic_1x2 | 3 | 0.4325 |
| 1902 s | persistence | 3 | 1.1215 |
| 1902 s | poisson | 3 | 1.2740 |
| 1902 s | uniform | 3 | 1.4469 |
| 1955 s | current_score | 3 | 11.5129 |
| 1955 s | historical_frequency | 3 | 1.7918 |
| 1955 s | laya | 3 | 0.3656 |
| 1955 s | logistic_1x2 | 3 | 0.7985 |
| 1955 s | persistence | 3 | 0.9570 |
| 1955 s | poisson | 3 | 0.3860 |
| 1955 s | uniform | 3 | 1.0414 |
| 2047 s | current_score | 3 | 11.5129 |
| 2047 s | historical_frequency | 3 | 1.1896 |
| 2047 s | laya | 3 | 0.6443 |
| 2047 s | logistic_1x2 | 3 | 0.0220 |
| 2047 s | persistence | 3 | 0.6803 |
| 2047 s | poisson | 3 | 0.6964 |
| 2047 s | uniform | 3 | 1.0414 |
| 2059 s | current_score | 3 | 11.5129 |
| 2059 s | historical_frequency | 3 | 1.2993 |
| 2059 s | laya | 3 | 0.4103 |
| 2059 s | logistic_1x2 | 3 | 0.3012 |
| 2059 s | persistence | 3 | 0.8192 |
| 2059 s | poisson | 3 | 0.4625 |
| 2059 s | uniform | 3 | 1.0414 |
| 2203 s | current_score | 3 | 11.5129 |
| 2203 s | historical_frequency | 3 | 1.2238 |
| 2203 s | laya | 3 | 0.3033 |
| 2203 s | logistic_1x2 | 3 | 0.1396 |
| 2203 s | persistence | 3 | 0.5964 |
| 2203 s | poisson | 3 | 0.3829 |
| 2203 s | uniform | 3 | 1.0414 |
| 2219 s | current_score | 3 | 11.5129 |
| 2219 s | historical_frequency | 3 | 1.1896 |
| 2219 s | laya | 3 | 0.6747 |
| 2219 s | logistic_1x2 | 3 | 0.0270 |
| 2219 s | persistence | 3 | 0.5702 |
| 2219 s | poisson | 3 | 0.6353 |
| 2219 s | uniform | 3 | 1.0414 |
| 2231 s | current_score | 3 | 11.5129 |
| 2231 s | historical_frequency | 3 | 1.3350 |
| 2231 s | laya | 3 | 0.4560 |
| 2231 s | logistic_1x2 | 3 | 0.3233 |
| 2231 s | persistence | 3 | 0.5211 |
| 2231 s | poisson | 3 | 0.4635 |
| 2231 s | uniform | 3 | 1.0414 |
| 2314 s | current_score | 3 | 23.0259 |
| 2314 s | historical_frequency | 3 | 1.0498 |
| 2314 s | laya | 3 | 1.3349 |
| 2314 s | logistic_1x2 | 3 | 0.3906 |
| 2314 s | persistence | 3 | 1.4351 |
| 2314 s | poisson | 3 | 1.3013 |
| 2314 s | uniform | 3 | 1.4469 |
| 2346 s | current_score | 3 | 11.5129 |
| 2346 s | historical_frequency | 3 | 1.4351 |
| 2346 s | laya | 3 | 0.4083 |
| 2346 s | logistic_1x2 | 3 | 0.1271 |
| 2346 s | persistence | 3 | 0.6214 |
| 2346 s | poisson | 3 | 0.4309 |
| 2346 s | uniform | 3 | 1.0414 |
| 2358 s | current_score | 3 | 11.5129 |
| 2358 s | historical_frequency | 3 | 1.4469 |
| 2358 s | laya | 3 | 0.5001 |
| 2358 s | logistic_1x2 | 3 | 0.0619 |
| 2358 s | persistence | 3 | 0.5992 |
| 2358 s | poisson | 3 | 0.3715 |
| 2358 s | uniform | 3 | 1.0414 |
| 2402 s | current_score | 3 | 11.5129 |
| 2402 s | historical_frequency | 3 | 1.2528 |
| 2402 s | laya | 3 | 0.4238 |
| 2402 s | logistic_1x2 | 3 | 0.3280 |
| 2402 s | persistence | 3 | 0.5290 |
| 2402 s | poisson | 3 | 0.4601 |
| 2402 s | uniform | 3 | 1.0414 |
| 2442 s | current_score | 3 | 0.0000 |
| 2442 s | historical_frequency | 3 | 1.2040 |
| 2442 s | laya | 3 | 0.7944 |
| 2442 s | logistic_1x2 | 3 | 0.6357 |
| 2442 s | persistence | 3 | 0.8336 |
| 2442 s | poisson | 3 | 0.7331 |
| 2442 s | uniform | 3 | 1.4469 |
| 2465 s | current_score | 3 | 11.5129 |
| 2465 s | historical_frequency | 3 | 1.1896 |
| 2465 s | laya | 3 | 0.5550 |
| 2465 s | logistic_1x2 | 3 | 0.0220 |
| 2465 s | persistence | 3 | 0.6568 |
| 2465 s | poisson | 3 | 0.6104 |
| 2465 s | uniform | 3 | 1.0414 |
| 2485 s | current_score | 3 | 11.5129 |
| 2485 s | historical_frequency | 3 | 1.4816 |
| 2485 s | laya | 3 | 0.4589 |
| 2485 s | logistic_1x2 | 3 | 0.4568 |
| 2485 s | persistence | 3 | 0.6714 |
| 2485 s | poisson | 3 | 0.4525 |
| 2485 s | uniform | 3 | 1.0414 |
| 2488 s | current_score | 3 | 34.5388 |
| 2488 s | historical_frequency | 3 | 1.2528 |
| 2488 s | laya | 3 | 0.6251 |
| 2488 s | logistic_1x2 | 3 | 0.1431 |
| 2488 s | persistence | 3 | 1.0516 |
| 2488 s | poisson | 3 | 0.6981 |
| 2488 s | uniform | 3 | 1.0414 |
| 2497 s | current_score | 3 | 23.0259 |
| 2497 s | historical_frequency | 3 | 1.0498 |
| 2497 s | laya | 3 | 1.2524 |
| 2497 s | logistic_1x2 | 3 | 0.3379 |
| 2497 s | persistence | 3 | 1.4101 |
| 2497 s | poisson | 3 | 1.2515 |
| 2497 s | uniform | 3 | 1.4469 |
| 2522 s | current_score | 3 | 34.5388 |
| 2522 s | historical_frequency | 3 | 1.5041 |
| 2522 s | laya | 3 | 0.6145 |
| 2522 s | logistic_1x2 | 3 | 0.8853 |
| 2522 s | persistence | 3 | 1.6437 |
| 2522 s | poisson | 3 | 0.6819 |
| 2522 s | uniform | 3 | 1.0414 |
| 2538 s | current_score | 3 | 11.5129 |
| 2538 s | historical_frequency | 3 | 1.0560 |
| 2538 s | laya | 3 | 0.3311 |
| 2538 s | logistic_1x2 | 3 | 0.0211 |
| 2538 s | persistence | 3 | 0.5451 |
| 2538 s | poisson | 3 | 0.3572 |
| 2538 s | uniform | 3 | 1.0414 |
| 2547 s | current_score | 3 | 11.5129 |
| 2547 s | historical_frequency | 3 | 1.4351 |
| 2547 s | laya | 3 | 0.4223 |
| 2547 s | logistic_1x2 | 3 | 0.1271 |
| 2547 s | persistence | 3 | 0.6145 |
| 2547 s | poisson | 3 | 0.4185 |
| 2547 s | uniform | 3 | 1.0414 |
| 2567 s | current_score | 3 | 11.5129 |
| 2567 s | historical_frequency | 3 | 1.0560 |
| 2567 s | laya | 3 | 0.5495 |
| 2567 s | logistic_1x2 | 3 | 0.0211 |
| 2567 s | persistence | 3 | 0.5149 |
| 2567 s | poisson | 3 | 0.5443 |
| 2567 s | uniform | 3 | 1.0414 |
| 2569 s | current_score | 3 | 34.5388 |
| 2569 s | historical_frequency | 3 | 1.2809 |
| 2569 s | laya | 3 | 0.7185 |
| 2569 s | logistic_1x2 | 3 | 1.3483 |
| 2569 s | persistence | 3 | 1.5335 |
| 2569 s | poisson | 3 | 0.8143 |
| 2569 s | uniform | 3 | 1.0414 |
| 2598 s | current_score | 3 | 11.5129 |
| 2598 s | historical_frequency | 3 | 1.5041 |
| 2598 s | laya | 3 | 0.5358 |
| 2598 s | logistic_1x2 | 3 | 0.8853 |
| 2598 s | persistence | 3 | 1.0195 |
| 2598 s | poisson | 3 | 0.5560 |
| 2598 s | uniform | 3 | 1.0414 |
| 2636 s | current_score | 3 | 23.0259 |
| 2636 s | historical_frequency | 3 | 1.1527 |
| 2636 s | laya | 3 | 2.6213 |
| 2636 s | logistic_1x2 | 3 | 1.9442 |
| 2636 s | persistence | 3 | 2.2789 |
| 2636 s | poisson | 3 | 2.6581 |
| 2636 s | uniform | 3 | 1.4469 |
| 2640 s | current_score | 3 | 34.5388 |
| 2640 s | historical_frequency | 3 | 1.1896 |
| 2640 s | laya | 3 | 0.6952 |
| 2640 s | logistic_1x2 | 3 | 0.0435 |
| 2640 s | persistence | 3 | 1.0928 |
| 2640 s | poisson | 3 | 0.6974 |
| 2640 s | uniform | 3 | 1.0414 |
| 2700 s | current_score | 120 | 15.2546 |
| 2700 s | historical_frequency | 120 | 1.2805 |
| 2700 s | laya | 120 | 0.8113 |
| 2700 s | logistic_1x2 | 120 | 0.6652 |
| 2700 s | persistence | 120 | 0.9280 |
| 2700 s | poisson | 120 | 0.8023 |
| 2700 s | uniform | 120 | 1.1529 |
| 2710 s | current_score | 3 | 0.0000 |
| 2710 s | historical_frequency | 3 | 1.0498 |
| 2710 s | laya | 3 | 1.1118 |
| 2710 s | logistic_1x2 | 3 | 0.3906 |
| 2710 s | persistence | 3 | 0.9413 |
| 2710 s | poisson | 3 | 1.0652 |
| 2710 s | uniform | 3 | 1.4469 |
| 2727 s | current_score | 3 | 0.0000 |
| 2727 s | historical_frequency | 3 | 1.2040 |
| 2727 s | laya | 3 | 0.6969 |
| 2727 s | logistic_1x2 | 3 | 0.6357 |
| 2727 s | persistence | 3 | 0.7756 |
| 2727 s | poisson | 3 | 0.6786 |
| 2727 s | uniform | 3 | 1.4469 |
| 2754 s | current_score | 3 | 11.5129 |
| 2754 s | historical_frequency | 3 | 1.7918 |
| 2754 s | laya | 3 | 0.3345 |
| 2754 s | logistic_1x2 | 3 | 0.7985 |
| 2754 s | persistence | 3 | 0.9081 |
| 2754 s | poisson | 3 | 0.3508 |
| 2754 s | uniform | 3 | 1.0414 |
| 2785 s | current_score | 3 | 11.5129 |
| 2785 s | historical_frequency | 3 | 1.0415 |
| 2785 s | laya | 3 | 0.3880 |
| 2785 s | logistic_1x2 | 3 | 0.1293 |
| 2785 s | persistence | 3 | 0.5245 |
| 2785 s | poisson | 3 | 0.4281 |
| 2785 s | uniform | 3 | 1.0414 |
| 2799 s | current_score | 3 | 11.5129 |
| 2799 s | historical_frequency | 3 | 1.4469 |
| 2799 s | laya | 3 | 0.5348 |
| 2799 s | logistic_1x2 | 3 | 0.1768 |
| 2799 s | persistence | 3 | 0.5677 |
| 2799 s | poisson | 3 | 0.4122 |
| 2799 s | uniform | 3 | 1.0414 |
| 2801 s | current_score | 3 | 11.5129 |
| 2801 s | historical_frequency | 3 | 1.5581 |
| 2801 s | laya | 3 | 1.0205 |
| 2801 s | logistic_1x2 | 3 | 3.6014 |
| 2801 s | persistence | 3 | 0.8731 |
| 2801 s | poisson | 3 | 0.9277 |
| 2801 s | uniform | 3 | 1.0414 |
| 2807 s | current_score | 3 | 11.5129 |
| 2807 s | historical_frequency | 3 | 1.4469 |
| 2807 s | laya | 3 | 0.4848 |
| 2807 s | logistic_1x2 | 3 | 0.0619 |
| 2807 s | persistence | 3 | 0.5847 |
| 2807 s | poisson | 3 | 0.3579 |
| 2807 s | uniform | 3 | 1.0414 |
| 2820 s | current_score | 3 | 11.5129 |
| 2820 s | historical_frequency | 3 | 1.4816 |
| 2820 s | laya | 3 | 0.5593 |
| 2820 s | logistic_1x2 | 3 | 0.2209 |
| 2820 s | persistence | 3 | 0.8753 |
| 2820 s | poisson | 3 | 0.5897 |
| 2820 s | uniform | 3 | 1.0414 |
| 2905 s | current_score | 3 | 0.0000 |
| 2905 s | historical_frequency | 3 | 0.9808 |
| 2905 s | laya | 3 | 1.1098 |
| 2905 s | logistic_1x2 | 3 | 0.3160 |
| 2905 s | persistence | 3 | 0.8459 |
| 2905 s | poisson | 3 | 1.0301 |
| 2905 s | uniform | 3 | 1.4469 |
| 2920 s | current_score | 3 | 11.5129 |
| 2920 s | historical_frequency | 3 | 1.2238 |
| 2920 s | laya | 3 | 0.3066 |
| 2920 s | logistic_1x2 | 3 | 0.1396 |
| 2920 s | persistence | 3 | 0.5773 |
| 2920 s | poisson | 3 | 0.3882 |
| 2920 s | uniform | 3 | 1.0414 |
| 2948 s | current_score | 3 | 0.0000 |
| 2948 s | historical_frequency | 3 | 1.3863 |
| 2948 s | laya | 3 | 1.1167 |
| 2948 s | logistic_1x2 | 3 | 0.3681 |
| 2948 s | persistence | 3 | 0.9346 |
| 2948 s | poisson | 3 | 1.0454 |
| 2948 s | uniform | 3 | 1.4469 |
| 2954 s | current_score | 3 | 11.5129 |
| 2954 s | historical_frequency | 3 | 1.3350 |
| 2954 s | laya | 3 | 0.5482 |
| 2954 s | logistic_1x2 | 3 | 0.3233 |
| 2954 s | persistence | 3 | 0.6660 |
| 2954 s | poisson | 3 | 0.5834 |
| 2954 s | uniform | 3 | 1.0414 |
| 2972 s | current_score | 3 | 11.5129 |
| 2972 s | historical_frequency | 3 | 1.2238 |
| 2972 s | laya | 3 | 0.3277 |
| 2972 s | logistic_1x2 | 3 | 0.1396 |
| 2972 s | persistence | 3 | 0.5768 |
| 2972 s | poisson | 3 | 0.3896 |
| 2972 s | uniform | 3 | 1.0414 |
| 2991 s | current_score | 3 | 11.5129 |
| 2991 s | historical_frequency | 3 | 1.3350 |
| 2991 s | laya | 3 | 0.8946 |
| 2991 s | logistic_1x2 | 3 | 5.1997 |
| 2991 s | persistence | 3 | 0.6664 |
| 2991 s | poisson | 3 | 0.8181 |
| 2991 s | uniform | 3 | 1.0414 |
| 3000 s | current_score | 90 | 18.4207 |
| 3000 s | historical_frequency | 90 | 1.3553 |
| 3000 s | laya | 90 | 0.5866 |
| 3000 s | logistic_1x2 | 90 | 0.4713 |
| 3000 s | persistence | 90 | 0.9183 |
| 3000 s | poisson | 90 | 0.6249 |
| 3000 s | uniform | 90 | 1.0414 |
| 3052 s | current_score | 3 | 11.5129 |
| 3052 s | historical_frequency | 3 | 1.1896 |
| 3052 s | laya | 3 | 1.0187 |
| 3052 s | logistic_1x2 | 3 | 0.0270 |
| 3052 s | persistence | 3 | 0.8141 |
| 3052 s | poisson | 3 | 0.9907 |
| 3052 s | uniform | 3 | 1.0414 |
| 3063 s | current_score | 3 | 23.0259 |
| 3063 s | historical_frequency | 3 | 1.0498 |
| 3063 s | laya | 3 | 1.5103 |
| 3063 s | logistic_1x2 | 3 | 0.3790 |
| 3063 s | persistence | 3 | 1.1742 |
| 3063 s | poisson | 3 | 1.4375 |
| 3063 s | uniform | 3 | 1.4469 |
| 3064 s | current_score | 6 | 17.2694 |
| 3064 s | historical_frequency | 6 | 1.1579 |
| 3064 s | laya | 6 | 1.4338 |
| 3064 s | logistic_1x2 | 6 | 2.0190 |
| 3064 s | persistence | 6 | 0.9967 |
| 3064 s | poisson | 6 | 1.3078 |
| 3064 s | uniform | 6 | 1.2442 |
| 3072 s | current_score | 3 | 11.5129 |
| 3072 s | historical_frequency | 3 | 1.2238 |
| 3072 s | laya | 3 | 0.4649 |
| 3072 s | logistic_1x2 | 3 | 0.1460 |
| 3072 s | persistence | 3 | 0.4723 |
| 3072 s | poisson | 3 | 0.4325 |
| 3072 s | uniform | 3 | 1.0414 |
| 3081 s | current_score | 3 | 34.5388 |
| 3081 s | historical_frequency | 3 | 1.1896 |
| 3081 s | laya | 3 | 0.7297 |
| 3081 s | logistic_1x2 | 3 | 0.0435 |
| 3081 s | persistence | 3 | 1.1602 |
| 3081 s | poisson | 3 | 0.7251 |
| 3081 s | uniform | 3 | 1.0414 |
| 3087 s | current_score | 3 | 34.5388 |
| 3087 s | historical_frequency | 3 | 1.2809 |
| 3087 s | laya | 3 | 0.8600 |
| 3087 s | logistic_1x2 | 3 | 1.3483 |
| 3087 s | persistence | 3 | 1.6228 |
| 3087 s | poisson | 3 | 0.9278 |
| 3087 s | uniform | 3 | 1.0414 |
| 3093 s | current_score | 3 | 23.0259 |
| 3093 s | historical_frequency | 3 | 1.0498 |
| 3093 s | laya | 3 | 1.2158 |
| 3093 s | logistic_1x2 | 3 | 0.3379 |
| 3093 s | persistence | 3 | 1.3767 |
| 3093 s | poisson | 3 | 1.2331 |
| 3093 s | uniform | 3 | 1.4469 |
| 3103 s | current_score | 3 | 11.5129 |
| 3103 s | historical_frequency | 3 | 1.3350 |
| 3103 s | laya | 3 | 0.8624 |
| 3103 s | logistic_1x2 | 3 | 3.6056 |
| 3103 s | persistence | 3 | 0.7549 |
| 3103 s | poisson | 3 | 0.8383 |
| 3103 s | uniform | 3 | 1.0414 |
| 3106 s | current_score | 3 | 11.5129 |
| 3106 s | historical_frequency | 3 | 1.2993 |
| 3106 s | laya | 3 | 0.5266 |
| 3106 s | logistic_1x2 | 3 | 0.2351 |
| 3106 s | persistence | 3 | 0.8221 |
| 3106 s | poisson | 3 | 0.5530 |
| 3106 s | uniform | 3 | 1.0414 |
| 3143 s | current_score | 3 | 11.5129 |
| 3143 s | historical_frequency | 3 | 1.0986 |
| 3143 s | laya | 3 | 0.3808 |
| 3143 s | logistic_1x2 | 3 | 0.1503 |
| 3143 s | persistence | 3 | 0.5555 |
| 3143 s | poisson | 3 | 0.3998 |
| 3143 s | uniform | 3 | 1.0414 |
| 3157 s | current_score | 3 | 11.5129 |
| 3157 s | historical_frequency | 3 | 1.5041 |
| 3157 s | laya | 3 | 0.3755 |
| 3157 s | logistic_1x2 | 3 | 0.8725 |
| 3157 s | persistence | 3 | 0.6204 |
| 3157 s | poisson | 3 | 0.4068 |
| 3157 s | uniform | 3 | 1.0414 |
| 3205 s | current_score | 3 | 11.5129 |
| 3205 s | historical_frequency | 3 | 1.2993 |
| 3205 s | laya | 3 | 0.9628 |
| 3205 s | logistic_1x2 | 3 | 0.2351 |
| 3205 s | persistence | 3 | 0.8825 |
| 3205 s | poisson | 3 | 1.0178 |
| 3205 s | uniform | 3 | 1.0414 |
| 3208 s | current_score | 3 | 34.5388 |
| 3208 s | historical_frequency | 3 | 1.1896 |
| 3208 s | laya | 3 | 0.7467 |
| 3208 s | logistic_1x2 | 3 | 0.0435 |
| 3208 s | persistence | 3 | 1.1855 |
| 3208 s | poisson | 3 | 0.7395 |
| 3208 s | uniform | 3 | 1.0414 |
| 3218 s | current_score | 3 | 0.0000 |
| 3218 s | historical_frequency | 3 | 1.1632 |
| 3218 s | laya | 3 | 0.9439 |
| 3218 s | logistic_1x2 | 3 | 0.3988 |
| 3218 s | persistence | 3 | 0.8541 |
| 3218 s | poisson | 3 | 0.8802 |
| 3218 s | uniform | 3 | 1.4469 |
| 3240 s | current_score | 3 | 11.5129 |
| 3240 s | historical_frequency | 3 | 1.3350 |
| 3240 s | laya | 3 | 0.5900 |
| 3240 s | logistic_1x2 | 3 | 0.3233 |
| 3240 s | persistence | 3 | 0.6594 |
| 3240 s | poisson | 3 | 0.5859 |
| 3240 s | uniform | 3 | 1.0414 |
| 3251 s | current_score | 3 | 11.5129 |
| 3251 s | historical_frequency | 3 | 1.4469 |
| 3251 s | laya | 3 | 0.4592 |
| 3251 s | logistic_1x2 | 3 | 0.1768 |
| 3251 s | persistence | 3 | 0.5023 |
| 3251 s | poisson | 3 | 0.4346 |
| 3251 s | uniform | 3 | 1.0414 |
| 3272 s | current_score | 3 | 34.5388 |
| 3272 s | historical_frequency | 3 | 1.4469 |
| 3272 s | laya | 3 | 0.9131 |
| 3272 s | logistic_1x2 | 3 | 0.0619 |
| 3272 s | persistence | 3 | 1.1762 |
| 3272 s | poisson | 3 | 0.7991 |
| 3272 s | uniform | 3 | 1.0414 |
| 3277 s | current_score | 3 | 34.5388 |
| 3277 s | historical_frequency | 3 | 1.2809 |
| 3277 s | laya | 3 | 0.8907 |
| 3277 s | logistic_1x2 | 3 | 1.3483 |
| 3277 s | persistence | 3 | 1.6656 |
| 3277 s | poisson | 3 | 0.9803 |
| 3277 s | uniform | 3 | 1.0414 |
| 3290 s | current_score | 3 | 11.5129 |
| 3290 s | historical_frequency | 3 | 1.3437 |
| 3290 s | laya | 3 | 0.9403 |
| 3290 s | logistic_1x2 | 3 | 0.0222 |
| 3290 s | persistence | 3 | 0.7912 |
| 3290 s | poisson | 3 | 1.0124 |
| 3290 s | uniform | 3 | 1.0414 |
| 3297 s | current_score | 6 | 11.5129 |
| 3297 s | historical_frequency | 6 | 1.3468 |
| 3297 s | laya | 6 | 0.8513 |
| 3297 s | logistic_1x2 | 6 | 0.4536 |
| 3297 s | persistence | 6 | 0.8399 |
| 3297 s | poisson | 6 | 0.8679 |
| 3297 s | uniform | 6 | 1.0414 |
| 3361 s | current_score | 3 | 11.5129 |
| 3361 s | historical_frequency | 3 | 1.1896 |
| 3361 s | laya | 3 | 0.5273 |
| 3361 s | logistic_1x2 | 3 | 0.0435 |
| 3361 s | persistence | 3 | 0.6184 |
| 3361 s | poisson | 3 | 0.5000 |
| 3361 s | uniform | 3 | 1.0414 |
| 3374 s | current_score | 3 | 23.0259 |
| 3374 s | historical_frequency | 3 | 1.0498 |
| 3374 s | laya | 3 | 1.5197 |
| 3374 s | logistic_1x2 | 3 | 0.3790 |
| 3374 s | persistence | 3 | 1.1753 |
| 3374 s | poisson | 3 | 1.4545 |
| 3374 s | uniform | 3 | 1.4469 |
| 3413 s | current_score | 3 | 11.5129 |
| 3413 s | historical_frequency | 3 | 1.0560 |
| 3413 s | laya | 3 | 0.4212 |
| 3413 s | logistic_1x2 | 3 | 0.0211 |
| 3413 s | persistence | 3 | 0.4845 |
| 3413 s | poisson | 3 | 0.4173 |
| 3413 s | uniform | 3 | 1.0414 |
| 3417 s | current_score | 3 | 11.5129 |
| 3417 s | historical_frequency | 3 | 1.0415 |
| 3417 s | laya | 3 | 0.4064 |
| 3417 s | logistic_1x2 | 3 | 0.1293 |
| 3417 s | persistence | 3 | 0.4762 |
| 3417 s | poisson | 3 | 0.4310 |
| 3417 s | uniform | 3 | 1.0414 |
| 3421 s | current_score | 3 | 0.0000 |
| 3421 s | historical_frequency | 3 | 1.3863 |
| 3421 s | laya | 3 | 0.9915 |
| 3421 s | logistic_1x2 | 3 | 0.3681 |
| 3421 s | persistence | 3 | 0.8049 |
| 3421 s | poisson | 3 | 0.8984 |
| 3421 s | uniform | 3 | 1.4469 |
| 3436 s | current_score | 3 | 11.5129 |
| 3436 s | historical_frequency | 3 | 1.0986 |
| 3436 s | laya | 3 | 0.3909 |
| 3436 s | logistic_1x2 | 3 | 0.1503 |
| 3436 s | persistence | 3 | 0.5597 |
| 3436 s | poisson | 3 | 0.4053 |
| 3436 s | uniform | 3 | 1.0414 |
| 3452 s | current_score | 3 | 34.5388 |
| 3452 s | historical_frequency | 3 | 1.2993 |
| 3452 s | laya | 3 | 0.5356 |
| 3452 s | logistic_1x2 | 3 | 0.1658 |
| 3452 s | persistence | 3 | 1.6350 |
| 3452 s | poisson | 3 | 0.5299 |
| 3452 s | uniform | 3 | 1.0414 |
| 3473 s | current_score | 3 | 0.0000 |
| 3473 s | historical_frequency | 3 | 1.1632 |
| 3473 s | laya | 3 | 0.8747 |
| 3473 s | logistic_1x2 | 3 | 0.3988 |
| 3473 s | persistence | 3 | 0.7823 |
| 3473 s | poisson | 3 | 0.8018 |
| 3473 s | uniform | 3 | 1.4469 |
| 3501 s | current_score | 3 | 11.5129 |
| 3501 s | historical_frequency | 3 | 1.4816 |
| 3501 s | laya | 3 | 0.4571 |
| 3501 s | logistic_1x2 | 3 | 0.2209 |
| 3501 s | persistence | 3 | 0.8153 |
| 3501 s | poisson | 3 | 0.4767 |
| 3501 s | uniform | 3 | 1.0414 |
| 3576 s | current_score | 3 | 11.5129 |
| 3576 s | historical_frequency | 3 | 1.2809 |
| 3576 s | laya | 3 | 0.3968 |
| 3576 s | logistic_1x2 | 3 | 1.3483 |
| 3576 s | persistence | 3 | 0.7850 |
| 3576 s | poisson | 3 | 0.4346 |
| 3576 s | uniform | 3 | 1.0414 |
| 3577 s | current_score | 3 | 11.5129 |
| 3577 s | historical_frequency | 3 | 1.2528 |
| 3577 s | laya | 3 | 0.4439 |
| 3577 s | logistic_1x2 | 3 | 0.4913 |
| 3577 s | persistence | 3 | 0.5264 |
| 3577 s | poisson | 3 | 0.4513 |
| 3577 s | uniform | 3 | 1.0414 |
| 3578 s | current_score | 3 | 11.5129 |
| 3578 s | historical_frequency | 3 | 1.3350 |
| 3578 s | laya | 3 | 0.8574 |
| 3578 s | logistic_1x2 | 3 | 3.6056 |
| 3578 s | persistence | 3 | 0.7427 |
| 3578 s | poisson | 3 | 0.8291 |
| 3578 s | uniform | 3 | 1.0414 |
| 3600 s | current_score | 120 | 13.5277 |
| 3600 s | historical_frequency | 120 | 1.2805 |
| 3600 s | laya | 120 | 0.7565 |
| 3600 s | logistic_1x2 | 120 | 0.6652 |
| 3600 s | persistence | 120 | 0.8644 |
| 3600 s | poisson | 120 | 0.7552 |
| 3600 s | uniform | 120 | 1.1529 |
| 3602 s | current_score | 3 | 11.5129 |
| 3602 s | historical_frequency | 3 | 1.2528 |
| 3602 s | laya | 3 | 0.7064 |
| 3602 s | logistic_1x2 | 3 | 0.4913 |
| 3602 s | persistence | 3 | 0.7201 |
| 3602 s | poisson | 3 | 0.6868 |
| 3602 s | uniform | 3 | 1.0414 |
| 3613 s | current_score | 3 | 0.0000 |
| 3613 s | historical_frequency | 3 | 1.1632 |
| 3613 s | laya | 3 | 0.6382 |
| 3613 s | logistic_1x2 | 3 | 0.3988 |
| 3613 s | persistence | 3 | 0.5435 |
| 3613 s | poisson | 3 | 0.4942 |
| 3613 s | uniform | 3 | 1.4469 |
| 3622 s | current_score | 3 | 0.0000 |
| 3622 s | historical_frequency | 3 | 1.0498 |
| 3622 s | laya | 3 | 0.8631 |
| 3622 s | logistic_1x2 | 3 | 0.3906 |
| 3622 s | persistence | 3 | 0.7027 |
| 3622 s | poisson | 3 | 0.8090 |
| 3622 s | uniform | 3 | 1.4469 |
| 3637 s | current_score | 3 | 0.0000 |
| 3637 s | historical_frequency | 3 | 0.9808 |
| 3637 s | laya | 3 | 0.8450 |
| 3637 s | logistic_1x2 | 3 | 0.3160 |
| 3637 s | persistence | 3 | 0.6512 |
| 3637 s | poisson | 3 | 0.7992 |
| 3637 s | uniform | 3 | 1.4469 |
| 3672 s | current_score | 3 | 0.0000 |
| 3672 s | historical_frequency | 3 | 1.1632 |
| 3672 s | laya | 3 | 0.6377 |
| 3672 s | logistic_1x2 | 3 | 0.3988 |
| 3672 s | persistence | 3 | 0.5285 |
| 3672 s | poisson | 3 | 0.4794 |
| 3672 s | uniform | 3 | 1.4469 |
| 3690 s | current_score | 3 | 34.5388 |
| 3690 s | historical_frequency | 3 | 1.3437 |
| 3690 s | laya | 3 | 23.2541 |
| 3690 s | logistic_1x2 | 3 | 0.0222 |
| 3690 s | persistence | 3 | 23.4687 |
| 3690 s | poisson | 3 | 23.2375 |
| 3690 s | uniform | 3 | 1.0414 |
| 3694 s | current_score | 3 | 11.5129 |
| 3694 s | historical_frequency | 3 | 1.2238 |
| 3694 s | laya | 3 | 0.4198 |
| 3694 s | logistic_1x2 | 3 | 0.1460 |
| 3694 s | persistence | 3 | 0.4831 |
| 3694 s | poisson | 3 | 0.4261 |
| 3694 s | uniform | 3 | 1.0414 |
| 3756 s | current_score | 3 | 0.0000 |
| 3756 s | historical_frequency | 3 | 1.0498 |
| 3756 s | laya | 3 | 0.7836 |
| 3756 s | logistic_1x2 | 3 | 0.3906 |
| 3756 s | persistence | 3 | 0.6617 |
| 3756 s | poisson | 3 | 0.7641 |
| 3756 s | uniform | 3 | 1.4469 |
| 3784 s | current_score | 3 | 11.5129 |
| 3784 s | historical_frequency | 3 | 1.5581 |
| 3784 s | laya | 3 | 0.9413 |
| 3784 s | logistic_1x2 | 3 | 3.6014 |
| 3784 s | persistence | 3 | 0.8494 |
| 3784 s | poisson | 3 | 0.9087 |
| 3784 s | uniform | 3 | 1.0414 |
| 3854 s | current_score | 3 | 0.0000 |
| 3854 s | historical_frequency | 3 | 1.3863 |
| 3854 s | laya | 3 | 0.6627 |
| 3854 s | logistic_1x2 | 3 | 0.2893 |
| 3854 s | persistence | 3 | 0.6418 |
| 3854 s | poisson | 3 | 0.6136 |
| 3854 s | uniform | 3 | 1.4469 |
| 3863 s | current_score | 3 | 11.5129 |
| 3863 s | historical_frequency | 3 | 1.0560 |
| 3863 s | laya | 3 | 0.3726 |
| 3863 s | logistic_1x2 | 3 | 0.0211 |
| 3863 s | persistence | 3 | 0.4957 |
| 3863 s | poisson | 3 | 0.3843 |
| 3863 s | uniform | 3 | 1.0414 |
| 3916 s | current_score | 3 | 11.5129 |
| 3916 s | historical_frequency | 3 | 1.4469 |
| 3916 s | laya | 3 | 0.5903 |
| 3916 s | logistic_1x2 | 3 | 0.1768 |
| 3916 s | persistence | 3 | 0.6508 |
| 3916 s | poisson | 3 | 0.5451 |
| 3916 s | uniform | 3 | 1.0414 |
| 3955 s | current_score | 3 | 0.0000 |
| 3955 s | historical_frequency | 3 | 1.0498 |
| 3955 s | laya | 3 | 0.4283 |
| 3955 s | logistic_1x2 | 3 | 0.3790 |
| 3955 s | persistence | 3 | 0.5092 |
| 3955 s | poisson | 3 | 0.4114 |
| 3955 s | uniform | 3 | 1.4469 |
| 3982 s | current_score | 3 | 11.5129 |
| 3982 s | historical_frequency | 3 | 1.1896 |
| 3982 s | laya | 3 | 0.7738 |
| 3982 s | logistic_1x2 | 3 | 0.0270 |
| 3982 s | persistence | 3 | 0.7246 |
| 3982 s | poisson | 3 | 0.7516 |
| 3982 s | uniform | 3 | 1.0414 |
| 4014 s | current_score | 3 | 34.5388 |
| 4014 s | historical_frequency | 3 | 1.2528 |
| 4014 s | laya | 3 | 0.9487 |
| 4014 s | logistic_1x2 | 3 | 0.1431 |
| 4014 s | persistence | 3 | 1.4083 |
| 4014 s | poisson | 3 | 1.0597 |
| 4014 s | uniform | 3 | 1.0414 |
| 4019 s | current_score | 3 | 11.5129 |
| 4019 s | historical_frequency | 3 | 1.0560 |
| 4019 s | laya | 3 | 0.7181 |
| 4019 s | logistic_1x2 | 3 | 0.0211 |
| 4019 s | persistence | 3 | 0.7123 |
| 4019 s | poisson | 3 | 0.7350 |
| 4019 s | uniform | 3 | 1.0414 |
| 4028 s | current_score | 3 | 34.5388 |
| 4028 s | historical_frequency | 3 | 1.5041 |
| 4028 s | laya | 3 | 0.9023 |
| 4028 s | logistic_1x2 | 3 | 0.6729 |
| 4028 s | persistence | 3 | 1.6849 |
| 4028 s | poisson | 3 | 1.0248 |
| 4028 s | uniform | 3 | 1.0414 |
| 4035 s | current_score | 3 | 34.5388 |
| 4035 s | historical_frequency | 3 | 1.1896 |
| 4035 s | laya | 3 | 23.3042 |
| 4035 s | logistic_1x2 | 3 | 0.0220 |
| 4035 s | persistence | 3 | 23.5504 |
| 4035 s | poisson | 3 | 23.2945 |
| 4035 s | uniform | 3 | 1.0414 |
| 4040 s | current_score | 3 | 23.0259 |
| 4040 s | historical_frequency | 3 | 1.1527 |
| 4040 s | laya | 3 | 1.6130 |
| 4040 s | logistic_1x2 | 3 | 1.9442 |
| 4040 s | persistence | 3 | 1.4140 |
| 4040 s | poisson | 3 | 1.6044 |
| 4040 s | uniform | 3 | 1.4469 |
| 4055 s | current_score | 3 | 23.0259 |
| 4055 s | historical_frequency | 3 | 1.1527 |
| 4055 s | laya | 3 | 1.5579 |
| 4055 s | logistic_1x2 | 3 | 1.9442 |
| 4055 s | persistence | 3 | 1.4156 |
| 4055 s | poisson | 3 | 1.6054 |
| 4055 s | uniform | 3 | 1.4469 |
| 4112 s | current_score | 3 | 11.5129 |
| 4112 s | historical_frequency | 3 | 1.4816 |
| 4112 s | laya | 3 | 0.3992 |
| 4112 s | logistic_1x2 | 3 | 0.4568 |
| 4112 s | persistence | 3 | 0.6953 |
| 4112 s | poisson | 3 | 0.4260 |
| 4112 s | uniform | 3 | 1.0414 |
| 4119 s | current_score | 3 | 11.5129 |
| 4119 s | historical_frequency | 3 | 1.1896 |
| 4119 s | laya | 3 | 0.6963 |
| 4119 s | logistic_1x2 | 3 | 0.0435 |
| 4119 s | persistence | 3 | 0.7206 |
| 4119 s | poisson | 3 | 0.7089 |
| 4119 s | uniform | 3 | 1.0414 |
| 4130 s | current_score | 3 | 11.5129 |
| 4130 s | historical_frequency | 3 | 1.0415 |
| 4130 s | laya | 3 | 0.6723 |
| 4130 s | logistic_1x2 | 3 | 0.1293 |
| 4130 s | persistence | 3 | 0.7072 |
| 4130 s | poisson | 3 | 0.6873 |
| 4130 s | uniform | 3 | 1.0414 |
| 4151 s | current_score | 3 | 11.5129 |
| 4151 s | historical_frequency | 3 | 1.2238 |
| 4151 s | laya | 3 | 0.4331 |
| 4151 s | logistic_1x2 | 3 | 0.1460 |
| 4151 s | persistence | 3 | 0.5228 |
| 4151 s | poisson | 3 | 0.4552 |
| 4151 s | uniform | 3 | 1.0414 |
| 4154 s | current_score | 3 | 34.5388 |
| 4154 s | historical_frequency | 3 | 1.0560 |
| 4154 s | laya | 3 | 23.3248 |
| 4154 s | logistic_1x2 | 3 | 0.0211 |
| 4154 s | persistence | 3 | 23.4993 |
| 4154 s | poisson | 3 | 23.3090 |
| 4154 s | uniform | 3 | 1.0414 |
| 4178 s | current_score | 3 | 0.0000 |
| 4178 s | historical_frequency | 3 | 1.3863 |
| 4178 s | laya | 3 | 0.6545 |
| 4178 s | logistic_1x2 | 3 | 0.3681 |
| 4178 s | persistence | 3 | 0.5522 |
| 4178 s | poisson | 3 | 0.6149 |
| 4178 s | uniform | 3 | 1.4469 |
| 4198 s | current_score | 3 | 11.5129 |
| 4198 s | historical_frequency | 3 | 1.7918 |
| 4198 s | laya | 3 | 0.3903 |
| 4198 s | logistic_1x2 | 3 | 0.7985 |
| 4198 s | persistence | 3 | 0.8797 |
| 4198 s | poisson | 3 | 0.4173 |
| 4198 s | uniform | 3 | 1.0414 |
| 4230 s | current_score | 3 | 11.5129 |
| 4230 s | historical_frequency | 3 | 1.2528 |
| 4230 s | laya | 3 | 0.4328 |
| 4230 s | logistic_1x2 | 3 | 0.1431 |
| 4230 s | persistence | 3 | 0.6345 |
| 4230 s | poisson | 3 | 0.4736 |
| 4230 s | uniform | 3 | 1.0414 |
| 4238 s | current_score | 3 | 11.5129 |
| 4238 s | historical_frequency | 3 | 1.3350 |
| 4238 s | laya | 3 | 0.8624 |
| 4238 s | logistic_1x2 | 3 | 5.1997 |
| 4238 s | persistence | 3 | 0.6705 |
| 4238 s | poisson | 3 | 0.8179 |
| 4238 s | uniform | 3 | 1.0414 |
| 4241 s | current_score | 3 | 23.0259 |
| 4241 s | historical_frequency | 3 | 1.0498 |
| 4241 s | laya | 3 | 1.2618 |
| 4241 s | logistic_1x2 | 3 | 0.3379 |
| 4241 s | persistence | 3 | 1.4106 |
| 4241 s | poisson | 3 | 1.3104 |
| 4241 s | uniform | 3 | 1.4469 |
| 4259 s | current_score | 3 | 11.5129 |
| 4259 s | historical_frequency | 3 | 1.2993 |
| 4259 s | laya | 3 | 0.3449 |
| 4259 s | logistic_1x2 | 3 | 0.3012 |
| 4259 s | persistence | 3 | 0.8307 |
| 4259 s | poisson | 3 | 0.3294 |
| 4259 s | uniform | 3 | 1.0414 |
| 4313 s | current_score | 3 | 11.5129 |
| 4313 s | historical_frequency | 3 | 1.0986 |
| 4313 s | laya | 3 | 0.4178 |
| 4313 s | logistic_1x2 | 3 | 0.1503 |
| 4313 s | persistence | 3 | 0.5442 |
| 4313 s | poisson | 3 | 0.4546 |
| 4313 s | uniform | 3 | 1.0414 |
| 4416 s | current_score | 3 | 0.0000 |
| 4416 s | historical_frequency | 3 | 1.1527 |
| 4416 s | laya | 3 | 0.5021 |
| 4416 s | logistic_1x2 | 3 | 1.9442 |
| 4416 s | persistence | 3 | 0.4242 |
| 4416 s | poisson | 3 | 0.4594 |
| 4416 s | uniform | 3 | 1.4469 |
| 4427 s | current_score | 3 | 11.5129 |
| 4427 s | historical_frequency | 3 | 1.2993 |
| 4427 s | laya | 3 | 0.3585 |
| 4427 s | logistic_1x2 | 3 | 0.3012 |
| 4427 s | persistence | 3 | 0.8514 |
| 4427 s | poisson | 3 | 0.3535 |
| 4427 s | uniform | 3 | 1.0414 |
| 4432 s | current_score | 3 | 11.5129 |
| 4432 s | historical_frequency | 3 | 1.3350 |
| 4432 s | laya | 3 | 0.8966 |
| 4432 s | logistic_1x2 | 3 | 5.1997 |
| 4432 s | persistence | 3 | 0.6964 |
| 4432 s | poisson | 3 | 0.8432 |
| 4432 s | uniform | 3 | 1.0414 |
| 4438 s | current_score | 3 | 11.5129 |
| 4438 s | historical_frequency | 3 | 1.5041 |
| 4438 s | laya | 3 | 0.4439 |
| 4438 s | logistic_1x2 | 3 | 0.8725 |
| 4438 s | persistence | 3 | 0.6818 |
| 4438 s | poisson | 3 | 0.4611 |
| 4438 s | uniform | 3 | 1.0414 |
| 4478 s | current_score | 3 | 11.5129 |
| 4478 s | historical_frequency | 3 | 1.5581 |
| 4478 s | laya | 3 | 0.9701 |
| 4478 s | logistic_1x2 | 3 | 3.6014 |
| 4478 s | persistence | 3 | 0.8861 |
| 4478 s | poisson | 3 | 0.9525 |
| 4478 s | uniform | 3 | 1.0414 |
| 4497 s | current_score | 3 | 0.0000 |
| 4497 s | historical_frequency | 3 | 1.0498 |
| 4497 s | laya | 3 | 0.5010 |
| 4497 s | logistic_1x2 | 3 | 0.3906 |
| 4497 s | persistence | 3 | 0.4018 |
| 4497 s | poisson | 3 | 0.4722 |
| 4497 s | uniform | 3 | 1.4469 |
| 4500 s | current_score | 120 | 12.9520 |
| 4500 s | historical_frequency | 120 | 1.2805 |
| 4500 s | laya | 120 | 2.3622 |
| 4500 s | logistic_1x2 | 120 | 0.6652 |
| 4500 s | persistence | 120 | 2.4944 |
| 4500 s | poisson | 120 | 2.3609 |
| 4500 s | uniform | 120 | 1.1529 |
| 4514 s | current_score | 3 | 11.5129 |
| 4514 s | historical_frequency | 3 | 1.4816 |
| 4514 s | laya | 3 | 0.4636 |
| 4514 s | logistic_1x2 | 3 | 0.4568 |
| 4514 s | persistence | 3 | 0.7631 |
| 4514 s | poisson | 3 | 0.4888 |
| 4514 s | uniform | 3 | 1.0414 |
| 4519 s | current_score | 3 | 11.5129 |
| 4519 s | historical_frequency | 3 | 1.5041 |
| 4519 s | laya | 3 | 0.6670 |
| 4519 s | logistic_1x2 | 3 | 0.8853 |
| 4519 s | persistence | 3 | 0.8485 |
| 4519 s | poisson | 3 | 0.6663 |
| 4519 s | uniform | 3 | 1.0414 |
| 4529 s | current_score | 3 | 11.5129 |
| 4529 s | historical_frequency | 3 | 1.0986 |
| 4529 s | laya | 3 | 0.7037 |
| 4529 s | logistic_1x2 | 3 | 0.1503 |
| 4529 s | persistence | 3 | 0.7245 |
| 4529 s | poisson | 3 | 0.6786 |
| 4529 s | uniform | 3 | 1.0414 |
| 4568 s | current_score | 3 | 0.0000 |
| 4568 s | historical_frequency | 3 | 1.1632 |
| 4568 s | laya | 3 | 0.4285 |
| 4568 s | logistic_1x2 | 3 | 0.3988 |
| 4568 s | persistence | 3 | 0.3953 |
| 4568 s | poisson | 3 | 0.3955 |
| 4568 s | uniform | 3 | 1.4469 |
| 4590 s | current_score | 3 | 11.5129 |
| 4590 s | historical_frequency | 3 | 1.3350 |
| 4590 s | laya | 3 | 0.6843 |
| 4590 s | logistic_1x2 | 3 | 0.3233 |
| 4590 s | persistence | 3 | 0.7526 |
| 4590 s | poisson | 3 | 0.7273 |
| 4590 s | uniform | 3 | 1.0414 |
| 4593 s | current_score | 3 | 11.5129 |
| 4593 s | historical_frequency | 3 | 1.0986 |
| 4593 s | laya | 3 | 0.6434 |
| 4593 s | logistic_1x2 | 3 | 0.1503 |
| 4593 s | persistence | 3 | 0.7315 |
| 4593 s | poisson | 3 | 0.6818 |
| 4593 s | uniform | 3 | 1.0414 |
| 4594 s | current_score | 3 | 34.5388 |
| 4594 s | historical_frequency | 3 | 1.1896 |
| 4594 s | laya | 3 | 23.4509 |
| 4594 s | logistic_1x2 | 3 | 0.0435 |
| 4594 s | persistence | 3 | 23.6345 |
| 4594 s | poisson | 3 | 23.4489 |
| 4594 s | uniform | 3 | 1.0414 |
| 4701 s | current_score | 3 | 11.5129 |
| 4701 s | historical_frequency | 3 | 1.4469 |
| 4701 s | laya | 3 | 0.7450 |
| 4701 s | logistic_1x2 | 3 | 0.1768 |
| 4701 s | persistence | 3 | 0.7698 |
| 4701 s | poisson | 3 | 0.7171 |
| 4701 s | uniform | 3 | 1.0414 |
| 4704 s | current_score | 3 | 11.5129 |
| 4704 s | historical_frequency | 3 | 1.2993 |
| 4704 s | laya | 3 | 0.6620 |
| 4704 s | logistic_1x2 | 3 | 0.2351 |
| 4704 s | persistence | 3 | 0.8222 |
| 4704 s | poisson | 3 | 0.6583 |
| 4704 s | uniform | 3 | 1.0414 |
| 4731 s | current_score | 3 | 11.5129 |
| 4731 s | historical_frequency | 3 | 1.2528 |
| 4731 s | laya | 3 | 0.6444 |
| 4731 s | logistic_1x2 | 3 | 0.3280 |
| 4731 s | persistence | 3 | 0.7145 |
| 4731 s | poisson | 3 | 0.6807 |
| 4731 s | uniform | 3 | 1.0414 |
| 4770 s | current_score | 3 | 23.0259 |
| 4770 s | historical_frequency | 3 | 0.9808 |
| 4770 s | laya | 3 | 2.0501 |
| 4770 s | logistic_1x2 | 3 | 0.4325 |
| 4770 s | persistence | 3 | 1.4389 |
| 4770 s | poisson | 3 | 1.9142 |
| 4770 s | uniform | 3 | 1.4469 |
| 4773 s | current_score | 3 | 11.5129 |
| 4773 s | historical_frequency | 3 | 1.2528 |
| 4773 s | laya | 3 | 0.7635 |
| 4773 s | logistic_1x2 | 3 | 0.4913 |
| 4773 s | persistence | 3 | 0.8244 |
| 4773 s | poisson | 3 | 0.7748 |
| 4773 s | uniform | 3 | 1.0414 |
| 4778 s | current_score | 3 | 11.5129 |
| 4778 s | historical_frequency | 3 | 1.4816 |
| 4778 s | laya | 3 | 0.4782 |
| 4778 s | logistic_1x2 | 3 | 0.2209 |
| 4778 s | persistence | 3 | 0.8606 |
| 4778 s | poisson | 3 | 0.4998 |
| 4778 s | uniform | 3 | 1.0414 |
| 4790 s | current_score | 3 | 34.5388 |
| 4790 s | historical_frequency | 3 | 1.3437 |
| 4790 s | laya | 3 | 23.4534 |
| 4790 s | logistic_1x2 | 3 | 0.0222 |
| 4790 s | persistence | 3 | 23.7029 |
| 4790 s | poisson | 3 | 23.4513 |
| 4790 s | uniform | 3 | 1.0414 |
| 4808 s | current_score | 3 | 11.5129 |
| 4808 s | historical_frequency | 3 | 1.1896 |
| 4808 s | laya | 3 | 0.6804 |
| 4808 s | logistic_1x2 | 3 | 0.0270 |
| 4808 s | persistence | 3 | 0.7811 |
| 4808 s | poisson | 3 | 0.6755 |
| 4808 s | uniform | 3 | 1.0414 |
| 4836 s | current_score | 3 | 11.5129 |
| 4836 s | historical_frequency | 3 | 1.0415 |
| 4836 s | laya | 3 | 0.7136 |
| 4836 s | logistic_1x2 | 3 | 0.1293 |
| 4836 s | persistence | 3 | 0.7636 |
| 4836 s | poisson | 3 | 0.7398 |
| 4836 s | uniform | 3 | 1.0414 |
| 4837 s | current_score | 3 | 11.5129 |
| 4837 s | historical_frequency | 3 | 1.2528 |
| 4837 s | laya | 3 | 0.7789 |
| 4837 s | logistic_1x2 | 3 | 0.4913 |
| 4837 s | persistence | 3 | 0.8465 |
| 4837 s | poisson | 3 | 0.7961 |
| 4837 s | uniform | 3 | 1.0414 |
| 4840 s | current_score | 3 | 11.5129 |
| 4840 s | historical_frequency | 3 | 1.2993 |
| 4840 s | laya | 3 | 0.6499 |
| 4840 s | logistic_1x2 | 3 | 0.2351 |
| 4840 s | persistence | 3 | 0.8558 |
| 4840 s | poisson | 3 | 0.6630 |
| 4840 s | uniform | 3 | 1.0414 |
| 4843 s | current_score | 3 | 11.5129 |
| 4843 s | historical_frequency | 3 | 1.4351 |
| 4843 s | laya | 3 | 0.5600 |
| 4843 s | logistic_1x2 | 3 | 0.1271 |
| 4843 s | persistence | 3 | 0.7655 |
| 4843 s | poisson | 3 | 0.5919 |
| 4843 s | uniform | 3 | 1.0414 |
| 4845 s | current_score | 3 | 0.0000 |
| 4845 s | historical_frequency | 3 | 0.9808 |
| 4845 s | laya | 3 | 0.2996 |
| 4845 s | logistic_1x2 | 3 | 0.4325 |
| 4845 s | persistence | 3 | 0.2632 |
| 4845 s | poisson | 3 | 0.2796 |
| 4845 s | uniform | 3 | 1.4469 |
| 4848 s | current_score | 3 | 0.0000 |
| 4848 s | historical_frequency | 3 | 0.9808 |
| 4848 s | laya | 3 | 0.2967 |
| 4848 s | logistic_1x2 | 3 | 0.4325 |
| 4848 s | persistence | 3 | 0.2619 |
| 4848 s | poisson | 3 | 0.2782 |
| 4848 s | uniform | 3 | 1.4469 |
| 4865 s | current_score | 3 | 11.5129 |
| 4865 s | historical_frequency | 3 | 1.5041 |
| 4865 s | laya | 3 | 0.5713 |
| 4865 s | logistic_1x2 | 3 | 0.6729 |
| 4865 s | persistence | 3 | 0.8733 |
| 4865 s | poisson | 3 | 0.6178 |
| 4865 s | uniform | 3 | 1.0414 |
| 4878 s | current_score | 3 | 0.0000 |
| 4878 s | historical_frequency | 3 | 1.3863 |
| 4878 s | laya | 3 | 0.2589 |
| 4878 s | logistic_1x2 | 3 | 0.2893 |
| 4878 s | persistence | 3 | 0.2487 |
| 4878 s | poisson | 3 | 0.2354 |
| 4878 s | uniform | 3 | 1.4469 |
| 4880 s | current_score | 3 | 11.5129 |
| 4880 s | historical_frequency | 3 | 1.2993 |
| 4880 s | laya | 3 | 0.4937 |
| 4880 s | logistic_1x2 | 3 | 0.1658 |
| 4880 s | persistence | 3 | 0.9230 |
| 4880 s | poisson | 3 | 0.4834 |
| 4880 s | uniform | 3 | 1.0414 |
| 4895 s | current_score | 3 | 34.5388 |
| 4895 s | historical_frequency | 3 | 1.1896 |
| 4895 s | laya | 3 | 23.5570 |
| 4895 s | logistic_1x2 | 3 | 0.0270 |
| 4895 s | persistence | 3 | 23.7424 |
| 4895 s | poisson | 3 | 23.5458 |
| 4895 s | uniform | 3 | 1.0414 |
| 4896 s | current_score | 3 | 11.5129 |
| 4896 s | historical_frequency | 3 | 1.4469 |
| 4896 s | laya | 3 | 0.6192 |
| 4896 s | logistic_1x2 | 3 | 0.0619 |
| 4896 s | persistence | 3 | 0.7701 |
| 4896 s | poisson | 3 | 0.6286 |
| 4896 s | uniform | 3 | 1.0414 |
| 4916 s | current_score | 3 | 11.5129 |
| 4916 s | historical_frequency | 3 | 1.5041 |
| 4916 s | laya | 3 | 0.6143 |
| 4916 s | logistic_1x2 | 3 | 0.6729 |
| 4916 s | persistence | 3 | 0.8914 |
| 4916 s | poisson | 3 | 0.6417 |
| 4916 s | uniform | 3 | 1.0414 |
| 4922 s | current_score | 3 | 0.0000 |
| 4922 s | historical_frequency | 3 | 1.0498 |
| 4922 s | laya | 3 | 0.2168 |
| 4922 s | logistic_1x2 | 3 | 0.3379 |
| 4922 s | persistence | 3 | 0.2288 |
| 4922 s | poisson | 3 | 0.1974 |
| 4922 s | uniform | 3 | 1.4469 |
| 4945 s | current_score | 3 | 34.5388 |
| 4945 s | historical_frequency | 3 | 1.1896 |
| 4945 s | laya | 3 | 23.5725 |
| 4945 s | logistic_1x2 | 3 | 0.0220 |
| 4945 s | persistence | 3 | 23.8475 |
| 4945 s | poisson | 3 | 23.5708 |
| 4945 s | uniform | 3 | 1.0414 |
| 4952 s | current_score | 3 | 11.5129 |
| 4952 s | historical_frequency | 3 | 1.2528 |
| 4952 s | laya | 3 | 0.6092 |
| 4952 s | logistic_1x2 | 3 | 0.1431 |
| 4952 s | persistence | 3 | 0.7585 |
| 4952 s | poisson | 3 | 0.6496 |
| 4952 s | uniform | 3 | 1.0414 |
| 4953 s | current_score | 3 | 11.5129 |
| 4953 s | historical_frequency | 3 | 1.4469 |
| 4953 s | laya | 3 | 0.6470 |
| 4953 s | logistic_1x2 | 3 | 0.0619 |
| 4953 s | persistence | 3 | 0.7955 |
| 4953 s | poisson | 3 | 0.6576 |
| 4953 s | uniform | 3 | 1.0414 |
| 5014 s | current_score | 3 | 11.5129 |
| 5014 s | historical_frequency | 3 | 1.4816 |
| 5014 s | laya | 3 | 0.6785 |
| 5014 s | logistic_1x2 | 3 | 0.4568 |
| 5014 s | persistence | 3 | 1.0325 |
| 5014 s | poisson | 3 | 0.7220 |
| 5014 s | uniform | 3 | 1.0414 |
| 5041 s | current_score | 3 | 11.5129 |
| 5041 s | historical_frequency | 3 | 1.5041 |
| 5041 s | laya | 3 | 0.6798 |
| 5041 s | logistic_1x2 | 3 | 0.8725 |
| 5041 s | persistence | 3 | 0.9174 |
| 5041 s | poisson | 3 | 0.7051 |
| 5041 s | uniform | 3 | 1.0414 |
| 5076 s | current_score | 3 | 11.5129 |
| 5076 s | historical_frequency | 3 | 1.5041 |
| 5076 s | laya | 3 | 0.7067 |
| 5076 s | logistic_1x2 | 3 | 0.6729 |
| 5076 s | persistence | 3 | 0.9759 |
| 5076 s | poisson | 3 | 0.7463 |
| 5076 s | uniform | 3 | 1.0414 |
| 5079 s | current_score | 3 | 11.5129 |
| 5079 s | historical_frequency | 3 | 1.2993 |
| 5079 s | laya | 3 | 0.6036 |
| 5079 s | logistic_1x2 | 3 | 0.1658 |
| 5079 s | persistence | 3 | 1.0262 |
| 5079 s | poisson | 3 | 0.6097 |
| 5079 s | uniform | 3 | 1.0414 |
| 5083 s | current_score | 3 | 0.0000 |
| 5083 s | historical_frequency | 3 | 1.0498 |
| 5083 s | laya | 3 | 0.1468 |
| 5083 s | logistic_1x2 | 3 | 0.3379 |
| 5083 s | persistence | 3 | 0.1550 |
| 5083 s | poisson | 3 | 0.1333 |
| 5083 s | uniform | 3 | 1.4469 |
| 5091 s | current_score | 3 | 11.5129 |
| 5091 s | historical_frequency | 3 | 1.4469 |
| 5091 s | laya | 3 | 0.9455 |
| 5091 s | logistic_1x2 | 3 | 0.1768 |
| 5091 s | persistence | 3 | 0.9732 |
| 5091 s | poisson | 3 | 0.9512 |
| 5091 s | uniform | 3 | 1.0414 |
| 5100 s | current_score | 120 | 11.2251 |
| 5100 s | historical_frequency | 120 | 1.2805 |
| 5100 s | laya | 120 | 3.4977 |
| 5100 s | logistic_1x2 | 120 | 0.6652 |
| 5100 s | persistence | 120 | 3.6181 |
| 5100 s | poisson | 120 | 3.5041 |
| 5100 s | uniform | 120 | 1.1529 |
| 5140 s | current_score | 3 | 11.5129 |
| 5140 s | historical_frequency | 3 | 1.2238 |
| 5140 s | laya | 3 | 0.8630 |
| 5140 s | logistic_1x2 | 3 | 0.1460 |
| 5140 s | persistence | 3 | 0.9665 |
| 5140 s | poisson | 3 | 0.8960 |
| 5140 s | uniform | 3 | 1.0414 |
| 5246 s | current_score | 3 | 11.5129 |
| 5246 s | historical_frequency | 3 | 1.2809 |
| 5246 s | laya | 3 | 1.0727 |
| 5246 s | logistic_1x2 | 3 | 1.3483 |
| 5246 s | persistence | 3 | 1.2620 |
| 5246 s | poisson | 3 | 1.0750 |
| 5246 s | uniform | 3 | 1.0414 |
| 5247 s | current_score | 3 | 11.5129 |
| 5247 s | historical_frequency | 3 | 1.5041 |
| 5247 s | laya | 3 | 0.9469 |
| 5247 s | logistic_1x2 | 3 | 0.8725 |
| 5247 s | persistence | 3 | 1.1997 |
| 5247 s | poisson | 3 | 0.9751 |
| 5247 s | uniform | 3 | 1.0414 |

**Par tier d'information (scope test) :**

| Tier | Modèle | Prédictions | Log loss 1X2 (moyenne) |
|---|---|---|---|
| A | current_score | 501 | 26.1971 |
| A | historical_frequency | 501 | 1.2822 |
| A | laya | 501 | 0.9879 |
| A | logistic_1x2 | 501 | 0.6225 |
| A | persistence | 501 | 1.3622 |
| A | poisson | 501 | 0.9977 |
| A | uniform | 501 | 1.1394 |
| B | current_score | 501 | 10.4788 |
| B | historical_frequency | 501 | 1.2822 |
| B | laya | 501 | 1.6761 |
| B | logistic_1x2 | 501 | 0.6225 |
| B | persistence | 501 | 1.7164 |
| B | poisson | 501 | 1.6667 |
| B | uniform | 501 | 1.1394 |
| C | current_score | 501 | 10.4788 |
| C | historical_frequency | 501 | 1.2822 |
| C | laya | 501 | 1.6756 |
| C | logistic_1x2 | 501 | 0.6225 |
| C | persistence | 501 | 1.7164 |
| C | poisson | 501 | 1.6667 |
| C | uniform | 501 | 1.1394 |

**Par compétition (scope test) :**

| Compétition | Modèle | Prédictions | Log loss 1X2 (moyenne) |
|---|---|---|---|
| Bundesliga | current_score | 306 | 18.3981 |
| Bundesliga | historical_frequency | 306 | 1.3026 |
| Bundesliga | laya | 306 | 1.7721 |
| Bundesliga | logistic_1x2 | 306 | 0.6071 |
| Bundesliga | persistence | 306 | 1.8930 |
| Bundesliga | poisson | 306 | 1.7650 |
| Bundesliga | uniform | 306 | 1.1408 |
| EPL | current_score | 294 | 15.1548 |
| EPL | historical_frequency | 294 | 1.2557 |
| EPL | laya | 294 | 1.4005 |
| EPL | logistic_1x2 | 294 | 0.8501 |
| EPL | persistence | 294 | 1.5857 |
| EPL | poisson | 294 | 1.3946 |
| EPL | uniform | 294 | 1.1201 |
| LaLiga | current_score | 306 | 13.6575 |
| LaLiga | historical_frequency | 306 | 1.2603 |
| LaLiga | laya | 306 | 1.2669 |
| LaLiga | logistic_1x2 | 306 | 0.5307 |
| LaLiga | persistence | 306 | 1.3586 |
| LaLiga | poisson | 306 | 1.2710 |
| LaLiga | uniform | 306 | 1.1806 |
| Ligue1 | current_score | 297 | 15.9320 |
| Ligue1 | historical_frequency | 297 | 1.3239 |
| Ligue1 | laya | 297 | 1.2075 |
| Ligue1 | logistic_1x2 | 297 | 0.6749 |
| Ligue1 | persistence | 297 | 1.3689 |
| Ligue1 | poisson | 297 | 1.1974 |
| Ligue1 | uniform | 297 | 1.1315 |
| SerieA | current_score | 300 | 15.4273 |
| SerieA | historical_frequency | 300 | 1.2686 |
| SerieA | laya | 300 | 1.5795 |
| SerieA | logistic_1x2 | 300 | 0.4566 |
| SerieA | persistence | 300 | 1.7820 |
| SerieA | poisson | 300 | 1.5841 |
| SerieA | uniform | 300 | 1.1225 |

Ventilations descriptives (moyennes sans intervalle) fournies par l'évaluateur ; ces tableaux alimentent la section 14 (exploratoire).

## 10. Calibration


| Modèle | ECE 1X2 | Observations | Bins | Découpage |
|---|---|---|---|---|
| current_score | 0.0200 | 1503 | 15 | equal-width |
| historical_frequency | 0.2459 | 1503 | 15 | equal-width |
| laya | 0.2683 | 1503 | 15 | equal-width |
| logistic_1x2 | 0.2149 | 1503 | 15 | equal-width |
| persistence | 0.2760 | 1503 | 15 | equal-width |
| poisson | 0.2723 | 1503 | 15 | equal-width |
| uniform | 0.2143 | 1503 | 15 | equal-width |

ECE calculé par l'évaluateur (bins annoncés, décision figée) ; un ECE plus faible indique une meilleure calibration.

## 11. Robustesse et réactions aux événements


- **Audit de répétition (§9.2) :** k = 5 sur 459 snapshots (part 0.1005) ; sorties identiques = True ; JS max = 0.0000 ; taux de changement de décision = 0.0000.
- **Paraphrases / réordonnancement / traduction (§13.1, §13.2) :** en attente d'exécution (aucune variante de formulation dans ce run — H4 non exécutée).
- **Réaction après but (§13.3, H3) :** variation moyenne de la probabilité du côté qui marque = 0.0712 sur 301 paires (laya, tier B, snapshots de but vs snapshot précédent). Analyse descriptive, sans interprétation causale.
- **Snapshots quasi identiques (§13.4) :** en attente d'exécution.

## 12. Analyse des erreurs


- **Réponses invalides Laya (§9.3) :** 0 sur 4569 (taux 0.0000, seuil 0.0500) ; aucune réponse n'est réparée ni renormalisée (§0.4).
- **Masse de queue moyenne (censure 21+/13+) :** corners = 0.0013 [0.0008 ; 0.0020] ; cartons = 0.0000 [0.0000 ; 0.0000].
- **MAE censurée moyenne (comptages) :** corners = 5.4202 [4.3989 ; 6.4467] ; cartons = 1.7495 [1.5079 ; 1.9858] ; buts = 1.2956 [1.0677 ; 1.5467].
- **Journal d'erreurs :** aucune erreur journalisée.
- Les erreurs de modèle et les données manquantes sont rapportées, jamais masquées par une imputation (§18).

## 13. Résultats confirmatoires


**Résultats confirmatoires — hypothèses H1 à H5 pré-enregistrées uniquement.** Toute autre comparaison figure en section 14 (exploratoire) et ne peut pas être présentée comme confirmatoire (§1.3, annexe B).

**H1_progression_temporelle — la log loss 1X2 diminue lorsque le cutoff passe de pré-match à 85 minutes**
- Statut : confirmatoire. Log loss 1X2 (scope test) = 1.2795 [0.8852 ; 1.7502]. La lecture par cutoff (section 9) permet de comparer pré-match et 85 minutes ; aucune conclusion n'est tirée ici à la place de l'évaluateur.

**H2_calibration — la calibration de Laya, mesurée par ECE et log loss, est meilleure que celle de la baseline historique à information identique**
- Statut : confirmatoire. ECE laya = 0.2683 ; ECE fréquence historique = 0.2459.

**H3_reaction_apres_but — après un but, la probabilité du vainqueur correspondant augmente en moyenne, toutes choses égales par ailleurs**
- Statut : confirmatoire (descriptif directionnel). Δ moyen probabilité du côté buteur = 0.0712 (301 paires) — sans lecture causale (§13.3).

**H4_robustesse — les paraphrases sémantiquement équivalentes ne modifient pas fortement la distribution prédictive**
- Statut : NON exécutée dans ce run (aucune variante de formulation pré-enregistrée n'a été soumise) — ne peut ni être validée ni être rejetée.

**H5_comptages — pour corners et cartons, la performance de Laya est comparée séparément à une baseline moyenne historique et à un modèle de comptage adapté**
- Statut : confirmatoire. Famille `corners_crps` (référence laya) : historical_frequency Δ = -1.3042 [-2.2492 ; -0.3509] (Holm : significatif) ; poisson Δ = -0.7232 [-1.0085 ; -0.4371] (Holm : significatif)

## 14. Analyses exploratoires


**Analyses exploratoires.** Les résultats ci-dessous ne font partie d'aucune hypothèse pré-enregistrée : ils sont descriptifs et ne peuvent pas être présentés comme confirmatoires (annexe B).

**Comparaisons par famille (Holm-Bonferroni, §12.5) :**
| Famille | Métrique | Référence | Modèle | Δ moyen | IC 95 % | Significatif (Holm) | p |
|---|---|---|---|---|---|---|---|
| 1x2_log_loss | log_loss_1x2 | laya | current_score | 13.7366 | [11.1410 ; 16.1512] | oui | 0.000500 |
| 1x2_log_loss | log_loss_1x2 | laya | historical_frequency | 0.0010 | [-0.4848 ; 0.4146] | non | 0.482259 |
| 1x2_log_loss | log_loss_1x2 | laya | logistic_1x2 | -0.6143 | [-1.2025 ; -0.1060] | oui | 0.011994 |
| 1x2_log_loss | log_loss_1x2 | laya | persistence | 0.1355 | [0.0480 ; 0.2337] | oui | 0.002499 |
| 1x2_log_loss | log_loss_1x2 | laya | poisson | -0.0071 | [-0.0221 ; 0.0092] | non | 0.190405 |
| 1x2_log_loss | log_loss_1x2 | laya | uniform | -0.1266 | [-0.6118 ; 0.2634] | non | 0.301849 |
| corners_crps | corners_crps | laya | current_score | 5.3678 | [5.0524 ; 5.6627] | oui | 0.000500 |
| corners_crps | corners_crps | laya | historical_frequency | -1.3042 | [-2.2492 ; -0.3509] | oui | 0.004998 |
| corners_crps | corners_crps | laya | persistence | -0.7232 | [-1.0085 ; -0.4371] | oui | 0.000500 |
| corners_crps | corners_crps | laya | poisson | -0.7232 | [-1.0085 ; -0.4371] | oui | 0.000500 |
| corners_crps | corners_crps | laya | uniform | -1.1260 | [-1.5740 ; -0.6456] | oui | 0.000500 |
| score_bucket_log_loss | score_bucket_log_loss | laya | current_score | 20.5699 | [17.3947 ; 23.2990] | oui | 0.000500 |
| score_bucket_log_loss | score_bucket_log_loss | laya | historical_frequency | 10.8238 | [6.1182 ; 15.5768] | oui | 0.000500 |
| score_bucket_log_loss | score_bucket_log_loss | laya | persistence | 0.2103 | [0.0584 ; 0.3710] | oui | 0.004498 |
| score_bucket_log_loss | score_bucket_log_loss | laya | poisson | 0.0008 | [-0.0421 ; 0.0460] | non | 0.496252 |
| score_bucket_log_loss | score_bucket_log_loss | laya | uniform | 0.7035 | [0.4847 ; 0.9235] | oui | 0.000500 |

Convention : différence = modèle − laya (>0 : moins bon que laya). Un test non significatif ne prouve pas l'équivalence.
- Ventilations par cutoff / compétition / tier : voir section 9 (descriptif).
- Réactions événementielles après carton rouge, penalty, remplacement : en attente d'exécution.

## 15. Limites


| # | Limite (§18) | Impact sur l'interprétation |
|---|---|---|
| 1 | Les données sportives publiques peuvent être incomplètes, corrigées après publication ou soumises à licence. | La couverture par strate et les exclusions doivent être consultées avant toute généralisation ; la licence de la source doit être citée. |
| 2 | La qualité apparente de Laya peut refléter des biais de couverture des compétitions ou des sources. | Les comparaisons entre compétitations/saisons peuvent confondre couverture des données et performance du modèle. |
| 3 | Les événements et statistiques live peuvent être publiés avec retard ; la disponibilité réelle doit être modélisée. | Les délais figés (30 s / 45 s / 96 min) bornent le réalisme des snapshots ; un retard supérieur dégraderait la comparabilité. |
| 4 | Les snapshots d'un même match ne constituent pas des observations indépendantes. | Les intervalles sont groupés par match (§11.2) ; les métriques par snapshot restent descriptives. |
| 5 | Une catégorie `other` ou une queue censurée limite l'interprétation du score ou de l'espérance. | Les espérances de comptages sont censurées aux seuils 21+ / 13+ et ne doivent pas être lues comme des espérances complètes. |
| 6 | Les effets après événement ne sont pas des effets causaux. | Les réactions événementielles (§13.3) sont descriptives : elles ne supportent aucune lecture contrefactuelle. |
| 7 | Les résultats ne doivent pas être présentés comme un conseil de pari ni comme une garantie de résultat. | Diffusion scientifique uniquement ; aucune utilisation décisionnelle ou commerciale n'est couverte par ce protocole. |
| 8 | Aucune donnée personnelle sensible n'est nécessaire ; les identifiants de joueurs doivent être pseudonymisés. | Les identifiants de joueurs du jeu de données sont pseudonymes synthétiques ; aucune donnée réelle n'est exposée. |
| 9 | Les erreurs de modèle et les données manquantes doivent être rapportées, pas masquées par une imputation opportuniste. | Les valeurs manquantes restent null (§7.2) ; les taux d'invalidité et les exclusions sont publiés dans ce rapport. |

## 16. Conclusion


Ce rapport documente un run exécutable de bout en bout du protocole v2.0.0 : collecte, nettoyage, contexte pré-match, snapshots anti-fuite, prédictions, baselines, évaluation et correction multiple sont traçables par artefacts hashés (§15).
Le périmètre observé est un jeu de données synthétique et un client mock déterministe : **aucune conclusion sur le système Laya réel, sa calibration réelle ou son utilité décisionnelle ne peut être tirée de ce run** (§0.3). Les résultats numériques valident la MÉTHODE (pipeline reproductible, contrôles anti-fuite, dénominateurs publiés), pas le modèle.
Aucun critère de blocage §11.4 n'a été déclenché sur ce run.

## 17. Annexes de reproductibilité


- **Run :** `local_smoke_run` ; généré le 2026-09-26T09:20:35Z (UTC).
- **Configuration :** `/home/z/my-project/laya-football-evaluation/configs/experiment.yaml` ; **manifeste :** `/home/z/my-project/laya-football-evaluation/experiment_manifest.json` ; seed = 20260925.
- **Commandes de reproduction (§16) :** `python -m src.storage.database init` puis `python -m agents.collector|cleaner|pre_match|snapshot|laya|baselines|evaluator|analyst --run-id local_smoke_run --config /home/z/my-project/laya-football-evaluation/configs/experiment.yaml` (ou `python -m agents.orchestrator --config /home/z/my-project/laya-football-evaluation/configs/experiment.yaml --run-id local_smoke_run`).

**Décisions figées du manifeste (annexe B) :**
| Décision | Valeur | Justification |
|---|---|---|
| blocking_and_resume_criteria | blocage si > 5 % de snapshots fuyants, > 10 % de matchs manquants dans une strate obligatoire, > 5 % de réponses invalides ; reprise = relance idempotente de l'étape (--resume, §0.4) | seuils §11.4 ; un checkpoint ou une tâche non versionné bloque également le run |
| bootstrap_replicates | 2000 réplications bootstrap groupées par match, alpha = 0.05 | minimum §12.5 ; les snapshots d'un même match ne sont pas indépendants (§11.2) |
| holm_bonferroni_families | une famille par cible (4 familles : 1x2, score_bucket, corners, yellow_cards), référence = laya | familles définies avant le test final (§12.5, agents/evaluator.py COMPARISON_FAMILIES) |
| laya_checkpoint | PINNED_CHECKPOINT (à remplacer à l'exécution réelle) | checkpoint du client mock déterministe ; le checkpoint réel du SDK sera figé et hashé avant la collecte (§2.1) |
| missing_data_rule | null, aucune imputation | les données manquantes sont rapportées, jamais masquées par une imputation opportuniste (§7.2, §18) |
| primary_and_secondary_source | principale = LOCAL_FILE (à remplacer : StatsBomb/API-Football/FBref à figer avant collecte) ; secondaire = à figer | source de démonstration locale (données synthétiques) ; les sources réelles doivent être figées avant tout test final (§3.2) |
| primary_metrics | 1x2 = log_loss ; score_bucket = log_loss ; corners = crps ; yellow_cards = crps | une métrique principale par cible (§12, §11.3) — les autres métriques sont secondaires/descriptives |
| question_wording_and_order | QUESTIONS_V1 figé en version v1 ; ordre des critères = listes canoniques SCORE_BUCKETS (17) / CORNER_LEVELS (22) / YELLOW_LEVELS (14) | wording versionné §8.5 (src/core/tasks.py) : toute modification créerait une v2, jamais une retouche silencieuse |
| repetition_count | audit de répétition k = 5 sur au moins 10 % des snapshots, échantillon déterministe stratifié par tier | règle §9.2 : sorties identiques → une requête suffit ; sinon k = 5 pour tous les snapshots ou règle d'agrégation figée avant le test |
| same_timestamp_events | ordre source (elapsed_seconds, source_event_id) conservé + snapshot agrégé de contrôle si plusieurs événements partagent le même instant | ordre documenté et reproductible (§6.2) ; la version agrégée permet de contrôler l'effet du choix d'ordre |
| seasons_and_competitions | saisons 2021-2022, 2022-2023, 2023-2024 ; compétitions EPL, LaLiga, SerieA, Bundesliga, Ligue1 | périmètre §3.1 : 3 saisons complètes sur les 5 grands championnats (split temporel possible §11.1) |
| second_yellow_card_convention | le deuxième carton jaune est compté comme jaune si identifiable, sinon analyse de sensibilité | convention §3.5 : le comptage des jaunes reste comparable entre source et cible ; l'analyse de sensibilité couvre les cas non identifiables |
| statistics_availability | événements publiés 30 s après l'instant de jeu, statistiques 45 s après, match terminé disponible 96 min après le coup d'envoi | délais de publication réels bornés, figés dans agents/cleaner.py (§3.2) — la disponibilité doit être modélisée, pas supposée instantanée |
| tail_thresholds | corners 21+ ; cartons jaunes 13+ | queues censurées figées (§8.3, §8.4, src/core/tasks.py) — les espérances dérivées sont censurées |
| temporal_split | entraînement = 2021-2022 et 2022-2023 ; test final = 2023-2024 ; matchs d'un même jour dans le même bloc | découpage temporel §11.1 (jamais de split aléatoire de snapshots) ; le test final n'est jamais consulté pour les choix de modèle |
| tiers_definition | A = bloc pré-match seul ; B = A + score, cartons, corners, événements ; C = B + tirs, tirs cadrés, possession, xG | niveaux d'information §6.3 — identiques pour Laya et les baselines (§10.4) |
| timezone_and_kickoff | tous les horodatages en UTC ISO-8601 « ...Z » ; kickoff = timestamp officiel du coup d'envoi fourni par la source | référence temporelle unique et comparable (§5.1) ; aucun fuseau local implicite |

**Hashes SHA-256 des artefacts sources :**
| Artefact | SHA-256 |
|---|---|
| baselines_run | bbbf1486373a71c2ff86fe51988080ded4af7ecc994c6801cc46df5bb41a58cf |
| cleaning_report | 63d1410962b6012c42f7af4334d9b3b9ec962da795210ec0845cc4abe5f0338d |
| collector_coverage | ad54f449cf9a7fa11485d2a8c8613e79b8197089c1e6662b434d9f1f893b5244 |
| evaluation_report | a9a31002fdfceb546f0e215fe64a7d4e40ec0a129efbc13ea9f8559dfa4c1cdb |
| laya_run | a6200769bd2ec2e46c3b9fd3f01376332d3043c34efc44b47e849d19452d8bdd |
| pre_match_validation | 1534b72df2c7d59fee422855e4221ea99aafa743651ac2d61dd21f35f2747bb0 |
| repetition_audit | 55843bde619e031fee1dbb66f935d7d2c98808b3b6d7364e7b2fa66383542359 |
| snapshot_validation | f6a9c8a4f1360dc1d57be2650b1e94c464a4fd4b76ff4445b2950c65406ea01d |

Une reproduction doit pouvoir repartir des fichiers bruts sans appeler de nouveau l'API externe (§17).
