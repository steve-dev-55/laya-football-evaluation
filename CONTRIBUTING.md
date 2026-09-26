# Contribuer à laya-football-evaluation

Merci de votre intérêt pour cette étude pré-enregistrée. Ce dépôt a une
exigence particulière : **l'intégrité scientifique du pré-enregistrement**.
Merci de lire ce guide avant toute contribution.

## 1. Statut du pré-enregistrement

Le protocole (v2.0.0, `PROTOCOLE_LAYA_FOOTBALL_AGENTS_IA.md`) et le manifeste
(`experiment_manifest.json`) sont **figés avant l'analyse du jeu de test**.
Conséquences :

- Toute modification du protocole, du manifeste ou des questions canoniques
  après la publication des résultats doit créer une **nouvelle version**
  et être marquée comme analyse post hoc dans les conclusions.
- Les corrections de bug qui changent un comportement documenté doivent être
  signalées dans `CHANGELOG.md` avec leur justification scientifique.
- Aucune décision analytique ne peut être prise après consultation des
  résultats du test final (règle anti-HARKing, protocole §0.4 et annexe B).

## 2. Flux de travail

1. Ouvrez une *issue* décrivant le problème ou l'amélioration.
2. Forkez, créez une branche `feat/...` ou `fix/...`.
3. Assurez `ruff check .` et `pytest` verts en local.
4. Ouvrez une *pull request* décrivant :
   - ce qui change ;
   - pourquoi cela ne viole pas le pré-enregistrement (ou quelles analyses
     deviennent post hoc).

La CI (GitHub Actions) exécute lint, tests unitaires, vérification anti-fuite
et un pipeline de bout en bout sur données synthétiques.

## 3. Conventions de code

- Python ≥ 3.10, typing annoté, docstrings concises.
- Identifiants déterministes SHA-256 (`src/core/ids.py`) — ne jamais
  introduire d'identifiant aléatoire dans les artefacts.
- Aucune donnée réelle commitée : les données brutes vivent hors git
  (`.gitignore`). Les tests utilisent des fixtures synthétiques.
- Les agents ne communiquent que par artefacts versionnés avec hash
  (protocole §14) — pas d'appels directs entre agents.

## 4. Signaler un problème scientifique

Fuite de données suspectée, erreur de métrique, violation du protocole :
ouvrez une issue avec le label `scientific-integrity`. Ces signalements ont
priorité absolue et sont consignés dans le rapport final si confirmés.

## 5. Licence

En contribuant, vous acceptez que votre contribution soit publiée sous
MIT (code) et CC-BY 4.0 (documentation, figures).
