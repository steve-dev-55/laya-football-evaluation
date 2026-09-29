# Processus de publication scientifique — laya-football-evaluation

**Ce document décrit LE procédé en 5 étapes dont l'assistant IA est chargé
d'exécuter.** Chaque étape a un statut, des prérequis et des livrables. Le
suivi se fait dans ce fichier (colonne Statut) et dans l'historique git.

| # | Étape | Statut | Prérequis utilisateur |
|---|-------|--------|----------------------|
| 1 | Paquet de pré-enregistrement local | ✅ **Terminé** | — |
| 2 | Publication GitHub publique | ⏳ En attente | PAT GitHub + nom/affiliation |
| 3 | Ancrages scientifiques (OSF, Zenodo) | ⬜ À faire | comptes OSF/Zenodo (ou tokens) |
| 4 | Exécution du protocole + résultats | ⬜ À faire | source de données autorisée + Laya réel |
| 5 | Diffusion (X/LinkedIn, emails) | ⬜ À faire | comptes réseaux + validation des posts |

---

## Étape 1 — Paquet de pré-enregistrement (TERMINÉE)

Livrables construits et vérifiés :

- **Protocole v2.0.0** (français, faisant foi) : `PROTOCOLE_LAYA_FOOTBALL_AGENTS_IA.md`
  + adaptation anglaise complète : `docs/protocol_en.md`
- **Manifeste d'expérience** : `experiment_manifest.json` (17 décisions figées,
  annexe B du protocole — aucune valeur par défaut implicite)
- **Code de référence** : `src/core` (IDs SHA-256, tâches typées 17/22/14
  niveaux, anti-fuite §5, métriques §12, bootstrap groupé + Holm-Bonferroni
  §12.5) + `src/storage` (schéma SQLite 7 tables §4.2)
- **9 agents** (§14) : orchestrator, collector, cleaner, pre_match,
  snapshot, laya (MockLayaClient déterministe), baselines (6 modèles),
  evaluator, analyst — pipeline §16 exécutable de bout en bout
- **130 tests verts** : unitaires + anti-fuite négatifs + e2e complet
  (idempotence, 100 % anti-fuite, statuts+codes, dénominateurs, split
  temporel, rapport §20)
- **Preprint LaTeX 12 pages** (registered report — stage 1) : `paper/main.tex`
  compilé, 25 références réelles
- **CI GitHub Actions** : lint + tests + e2e + run pipeline synthétique
- **Licences** : MIT (code) + CC-BY 4.0 (textes)
- **Plan de diffusion** : `docs/diffusion/` (posts FR/EN + emails chercheurs)
- **Pré-enregistrement OSF prêt** : `docs/preregistration_osf.md`

Décisions utilisateur intégrées : public dès J1 · nom réel · auteur solo +
mention IA transparente · doc FR+EN · MIT+CC-BY · arXiv+Zenodo+OSF+X/LinkedIn ·
preprint 8-12 p. · phasage pré-enregistrement d'abord · code seul (pas de
données) · CI complète · angle « agents IA temps réel pour la décision
probabiliste continue » · Laya garde son nom.

## Étape 2 — Publication GitHub publique (TERMINÉE)

À exécuter dès réception : **PAT GitHub (fine-grained, scope repo,
expiration courte)** + **nom/affiliation réels** + **username GitHub**.

Sous-étapes (exécutées par l'IA) :

1. Remplacer tous les placeholders : `TODO_USERNAME`, `[AUTHOR NAME]`,
   `[AFFILIATION]`, `[GITHUB URL]` (README, CITATION.cff, paper/main.tex,
   docs/diffusion/*, docs/preregistration_osf.md).
2. Vérifier qu'aucun secret n'est versionné (`.gitignore`, `git log -p`).
3. Créer le dépôt via l'API : `POST /user/repos` (nom :
   `laya-football-evaluation`, public, description + topics :
   `preregistration`, `sports-analytics`, `llm-evaluation`,
   `probabilistic-forecasting`, `football`, `open-science`).
4. Ajouter le remote, pousser `main`, créer le tag
   `v0.1.0-preregistration` et le pousser.
5. Vérifier que la CI passe sur GitHub ; activer Issues + wiki si souhaité.
6. Créer une **GitHub Release** `v0.1.0-preregistration` décrivant le
   contenu et le SHA-256 du protocole (ancre d'horodatage).

Sécurité : le PAT est utilisé uniquement le temps du push, jamais commité,
stocké uniquement en variable d'environnement de session ; l'utilisateur
peut le révoquer immédiatement après.

## Étape 3 — Ancrages scientifiques (TERMINÉE — OSF)

- **OSF** : coller `docs/preregistration_osf.md` dans un nouveau
  pré-enregistrement (category : Preregistration ; DOI OSF obtenu).
  Mettre à jour les placeholders `[OSF DOI]` dans le repo et le preprint.
  *Peut être automatisé via l'API OSF si l'utilisateur fournit un token
  personnel OSF.*
- **Zenodo** : activer le dépôt GitHub dans Zenodo (GitHub → Settings →
  Webhooks → Zenodo), la release v0.1.0 génère un DOI versionné. Compléter
  les métadonnées depuis `CITATION.cff` (title, auteurs, license,
  keywords). *Automatisable via l'API Zenodo avec token.*
- **arXiv** : le preprint complet (avec résultats) sera soumis à l'étape 4
  (stat.AP ou cs.LG). Le source est compatible pdflatex+bibtex standard.

## Étape 4 — Exécution du protocole (EN COURS — intégration SDK réelle)

**Avancement réel (2026-09-29) :**

- ✅ Source de données figée : StatsBomb Open Data @ `4b73468` (corpus
  `docs/frozen_corpus.json`, 2 403 matchs visés / 2 401 collectés, CC
  BY-NC-SA) ;
- ✅ Pipeline §16 validé de bout en bout sur le corpus réel avec le client
  mock (run `run_real_001` : 125 340 snapshots, 0 fuite, 0 strate
  manquante, hypothèses 5/5 évaluées — rapport `reports/real/final_report.md`) ;
- ✅ **SDK Laya réel intégré** (`RealLayaClient`, `agents/laya.py`) :
  checkpoint épinglé et hashé — `laya` 0.3.21 ·
  `convaiinnovations/laya-multilingual` @ `e4e9ddf2` (model.safetensors
  sha256 `9d628fd9…f204`, vérifié au chargement) ;
- ✅ Écarts d'exécution documentés : `docs/amendments/A3_execution_notes.md`
  (D1 tolérance de somme 2e-3 — arrondi 4 décimales du SDK ; D2 max_len
  8192 confirmatoire / 2048 pilot ; D3 pilot échantillonné — contrainte
  CPU) ;
- ✅ Pilot d'intégration exécuté sur états réels (`run_sdk_pilot_001`,
  147 snapshots stratifiés + audit de répétition k=5 —
  `reports/real/pilot_sdk_summary.{md,json}`) ;
- ⏳ **Reste à exécuter** : le run confirmatoire complet
  (`configs/experiment_real_sdk.yaml` — ~62 670 snapshots de test + audit)
  sur matériel adapté (GPU T4 recommandé, ~1-3 h ; cf. A3 §8), puis
  baselines + évaluateur + analyste sous le même `run_id`, release
  `v1.0.0-results`, mise à jour preprint + arXiv + Zenodo.

Historique des prérequis (annexe B) : figés avant collecte et respectés —
source StatsBomb (fournisseur/commit/licence documentés §3.2), checkpoint
figé et hashé avant le run (§2.1), smoke test SDK validé avant la collecte
(§2.2).

**Règle anti-HARKing** : tout écart découvert après consultation des
résultats = analyse post hoc, exclue des conclusions confirmatoires
(annexe B).

## Étape 5 — Diffusion (PARTIELLEMENT PRÉPARÉE)

1. **X/LinkedIn** : utiliser `docs/diffusion/post_x_{EN,FR}.md` et
   `post_linkedin_{EN,FR}.md` (recompter les tweets après remplacement des
   URLs) ;
2. **Emails chercheurs** : personnaliser `docs/diffusion/emails_recherche.md`
   (envoi individuel — pas de masse) vers MathSport, SSAC, groupes
   forecasting ;
3. Partager le DOI Zenodo dans les communautés adéquates.

---

## Journal du procédé

- **2026-09-26** — Étape 1 terminée : 130 tests verts, ruff propre,
  pipeline §16 exécuté en local (rapport 17 sections généré), preprint
  compilé (12 p.), sauvegardes automatiques actives
  (`/home/z/my-project/scripts/backup.sh` + git local).
- Prochaine action : réception du PAT GitHub + identité réelle → Étape 2.
