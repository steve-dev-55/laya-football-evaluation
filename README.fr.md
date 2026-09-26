# Évaluation Laya Football (version française)

**Protocole pré-enregistré multi-agents pour évaluer un moteur de décision IA comme prédicteur probabiliste de football en temps réel.**

> 📌 **Statut — Étape 1 (pré-enregistrement).** Le protocole, l'implémentation
> de référence et les tests sont publiés **avant** l'exécution de l'étude sur
> données réelles. Les résultats suivront dans une release séparée
> (`v1.0.0-results`). Voir [docs/publication_process.md](docs/publication_process.md).
> Documentation complète en anglais : [README.md](README.md) ·
> Protocole original (français, faisant foi) : [PROTOCOLE_LAYA_FOOTBALL_AGENTS_IA.md](PROTOCOLE_LAYA_FOOTBALL_AGENTS_IA.md)

## De quoi s'agit-il ?

Un moteur de décision IA « typé » (un système basé LLM qui renvoie des
distributions de probabilités plutôt que du texte libre) peut-il servir de
**prédicteur probabiliste en temps réel** pendant un match de football ?
Ce dépôt apporte une réponse rigoureuse et pré-enregistrée :

- **Quatre cibles** évaluées à **sept cutoffs en cours de match** (0, 15,
  30, 45, 60, 75, 85 minutes) plus des snapshots événementiels (buts,
  cartons rouges, penalties, remplacements) : 1X2, buckets de score
  (17 catégories), corners (22 niveaux, queue `21+`), cartons jaunes
  (14 niveaux, queue `13+`).
- **Trois tiers d'information** (A pré-match, B live minimal, C live
  complet avec xG/possession) — ablation de ce qui conduit réellement la
  qualité prédictive.
- **Garanties point-in-time** : aucun snapshot ne contient d'information
  postérieure à son cutoff (100 % audités, §5 du protocole).
- **Baselines équitables** recevant exactement la même information :
  uniforme, fréquences historiques, persistance du score, persistance des
  comptages, Poisson indépendant, régression logistique multinomiale.
- **Inférence groupée** : bootstrap stratifié par match (≥ 2 000
  réplications), correction Holm-Bonferroni sur les familles
  pré-enregistrées — les snapshots ne sont jamais traités comme des
  observations indépendantes.

## Démarrage rapide

```bash
pip install numpy scipy pandas scikit-learn PyYAML pytest ruff
bash scripts/run_pipeline.sh demo_run    # pipeline complet sur données synthétiques
cat reports/final_report.md              # rapport final 17 sections (§20)
python -m pytest tests/ -q               # 130 tests (unitaires + anti-fuite + e2e)
```

> Le run de démonstration utilise un **client Laya mock déterministe** et des
> données synthétiques. L'exécution réelle exige de figer le
> modèle/checkpoint et une source autorisée (voir
> [docs/publication_process.md](docs/publication_process.md), étape 4).

## Intégrité scientifique

- **Hypothèses figées d'abord** : H1-H5 écrites dans le manifeste avant
  toute évaluation du test final ; le reste est exploratoire par définition.
- **Aucune réparation silencieuse** : les réponses invalides sont
  enregistrées avec leur code d'erreur protocole, jamais renormalisées.
- **Seuils de blocage** : > 5 % de snapshots fuyards, > 10 % de matchs
  manquants ou > 5 % de réponses invalides bloquent le test final.
- **Tout est hashé** : chaque artefact porte son SHA-256 ; un tiers peut
  reproduire les métriques à partir des artefacts conservés.

## Licences

- **Code** : [MIT](LICENSE) — **Protocole, docs, figures, article** :
  [CC-BY 4.0](LICENSE-CC-BY-4.0)

## Avertissement

Étude scientifique de la qualité de prévision probabiliste. Ceci n'est pas
un conseil de pari et n'implique aucune garantie de résultat (protocole §18).
