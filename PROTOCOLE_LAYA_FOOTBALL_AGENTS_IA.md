# Protocole expérimental reproductible

## Évaluation de Laya comme moteur de décision probabiliste appliqué au football

**Version :** 2.0.0
**Statut :** protocole opérationnel à pré-enregistrer avant l'analyse du jeu de test
**Langue de travail :** français pour la documentation, anglais recommandé pour les questions canoniques envoyées au modèle
**Unité d'analyse :** match et snapshot de match
**Cible :** agents IA spécialisés opérant via des artefacts partagés

---

## 0. Objet et principes directeurs

### 0.1 Objectif

Mesurer si Laya produit, à plusieurs instants d'un match de football, des distributions prédictives :

1. calibrées ;
2. discriminantes ;
3. cohérentes avec l'information disponible ;
4. stables sous des variations de formulation ;
5. compétitives par rapport à des baselines statistiques reproduisibles.

Les cibles principales sont le résultat final 1X2, le score final regroupé, le total de corners et le total de cartons jaunes.

### 0.2 Règle centrale

À un cutoff `t`, aucun artefact transmis à Laya, aucune feature de baseline et aucun paramètre de sélection de modèle ne doit dépendre d'une information postérieure à `t` pour les données live, ou postérieure à l'heure de coupure pré-match pour les données historiques.

Le résultat final est utilisé uniquement après l'inférence, lors de l'évaluation.

### 0.3 Ce que l'étude peut et ne peut pas conclure

L'étude peut estimer la qualité prédictive hors échantillon de Laya sur les compétitions et saisons retenues.

Elle ne permet pas, à elle seule, de conclure à une causalité, à une rentabilité de pari, à une supériorité universelle de Laya, ni à une qualité générale du modèle sur d'autres domaines.

### 0.4 Principes non négociables

- Les données brutes sont immuables et conservées avant toute transformation.
- Chaque variable porte une provenance et une heure de disponibilité.
- Les pipelines sont idempotents : relancer un agent ne doit pas dupliquer les lignes ni modifier les artefacts validés.
- Toute réponse Laya invalide est enregistrée comme invalide ; elle n'est jamais réparée silencieusement.
- Les décisions analytiques principales sont figées avant consultation du test final.
- Les intervalles de confiance sont groupés par match, jamais calculés comme si les snapshots étaient indépendants.
- Les baselines et Laya reçoivent exactement le même niveau d'information au même cutoff.
- Les conclusions distinguent toujours observation, résultat statistique et hypothèse.

---

## 1. Questions de recherche et hypothèses pré-enregistrées

### 1.1 Question principale

À information disponible à la minute `t`, Laya produit-il des distributions prédictives mieux calibrées et/ou plus discriminantes que les baselines pré-définies pour :

- le résultat final 1X2 ;
- le score final regroupé ;
- le total de corners ;
- le total de cartons jaunes ?

### 1.2 Questions secondaires

- La qualité s'améliore-t-elle avec l'avancement du match ?
- Laya réagit-il dans le sens attendu après un but, un carton rouge, un penalty ou un remplacement ?
- La distribution reste-t-elle stable sous paraphrase, réordonnancement des champs et traduction contrôlée ?
- Quel niveau d'information est nécessaire pour atteindre une qualité donnée ?
- Les erreurs sont-elles concentrées dans des matchs, compétitions, équipes ou états particuliers ?
- Laya est-il mieux calibré, mais moins discriminant, ou inversement, que les baselines ?

### 1.3 Hypothèses confirmatoires

Les hypothèses suivantes doivent être écrites dans le manifeste de l'expérience avant l'évaluation du test final.

- **H1 — progression temporelle :** la log loss 1X2 diminue lorsque le cutoff passe de pré-match à 85 minutes.
- **H2 — calibration :** la calibration de Laya, mesurée par ECE et log loss, est meilleure que celle de la baseline historique à information identique.
- **H3 — réaction aux événements :** après un but, la probabilité du vainqueur correspondant augmente en moyenne, toutes choses égales par ailleurs.
- **H4 — robustesse :** les paraphrases sémantiquement équivalentes ne modifient pas fortement la distribution prédictive.
- **H5 — comptages :** pour corners et cartons, la performance de Laya est comparée séparément à une baseline moyenne historique et à un modèle de comptage adapté.

Une hypothèse non prévue dans le manifeste est exploratoire et ne doit pas être présentée comme confirmatoire.

---

## 2. Système sous test : Laya

### 2.1 Métadonnées obligatoires

Avant toute requête, l'agent Laya enregistre :

- nom exact du package et version installée ;
- hash ou identifiant exact du checkpoint ;
- variante utilisée : `laya`, `laya-multilingual` ou autre ;
- longueur maximale de contexte ;
- version Python et dépendances principales ;
- configuration du routeur ;
- date d'exécution et identifiant de run ;
- paramètres d'inférence, y compris batch et éventuelle seed.

Les caractéristiques architecturales annoncées dans la documentation ne sont pas considérées comme des faits expérimentaux tant qu'elles ne sont pas vérifiées dans l'environnement installé.

### 2.2 Validation du SDK avant la collecte

Un test de fumée doit confirmer :

1. le nom d'import réel ;
2. la signature réelle de `Router.predict` ;
3. les types acceptés par `questions` ;
4. le format de sortie ;
5. le comportement sur une question invalide ;
6. la reproductibilité de deux requêtes identiques ;
7. la conservation des probabilités et des clés de sortie.

Le type booléen doit être nommé selon le SDK réellement installé. Le terme `noul` du protocole initial ne doit pas être utilisé tant qu'il n'est pas confirmé par l'API ; dans le présent document, on parle de **booléen**.

### 2.3 Nature des sorties

Laya est évalué comme moteur de décision typée, et non comme générateur de texte. L'agent doit conserver la réponse brute et produire une représentation normalisée uniquement après validation du contrat de sortie.

La confiance fournie par Laya est une sortie secondaire. Elle ne remplace ni une mesure de calibration, ni une probabilité utilisée directement dans les métriques.

---

## 3. Périmètre des données

### 3.1 Compétitions et période

Périmètre recommandé :

- Premier League ;
- La Liga ;
- Serie A ;
- Bundesliga ;
- Ligue 1 ;
- trois saisons complètes, définies explicitement dans `experiment_manifest.json`.

L'objectif initial de 1 000 matchs est un objectif de puissance, pas un quota permettant de conserver des matchs de qualité insuffisante. Le nombre final de matchs inclus, exclus et manquants doit être rapporté par compétition et saison.

### 3.2 Sources

Une source principale est choisie avant la collecte. Une source secondaire sert à vérifier les résultats et les événements, mais ne doit pas compléter silencieusement la source principale.

Chaque enregistrement source doit contenir :

- fournisseur ;
- endpoint ou fichier ;
- identifiant source ;
- date de récupération ;
- statut HTTP ou code d'erreur ;
- hash SHA-256 du contenu brut ;
- licence et restrictions d'utilisation connues.

Sources possibles : StatsBomb, API-Football, FBref ou autre source documentée. La qualité et le contrat de licence doivent être vérifiés avant l'usage.

### 3.3 Règles d'inclusion

Inclure uniquement les matchs :

- terminés et officiellement homologués ;
- joués sans prolongation ;
- disposant du score final ;
- disposant d'événements et de statistiques nécessaires ;
- disposant d'un horodatage suffisamment précis pour le cutoff ;
- dont les identifiants domicile/extérieur sont résolus de façon unique.

### 3.4 Règles d'exclusion

Exclure et journaliser :

- matchs arrêtés, reportés, rejoués ou abandonnés ;
- matchs avec prolongation ou séance de tirs au but ;
- incohérence entre score final et événements ;
- absence d'une variable cible non imputable ;
- timestamps impossibles ou incompatibles avec la durée du match ;
- doublons non résolus ;
- données agrégées uniquement après le match pour un snapshot qui les exigerait avant le match.

Les matchs exclus ne doivent pas être remplacés après consultation des résultats.

### 3.5 Convention de comptage

- Les buts de jeu, penalties et buts contre son camp sont comptés comme buts de l'équipe bénéficiaire dans le score officiel des 90 minutes plus arrêts de jeu.
- Les tirs au but de la séance de penalty ne sont pas des buts de match.
- Les corners sont comptés par équipe et agrégés au total.
- Les cartons jaunes attribués aux joueurs sont comptés.
- Un deuxième avertissement au même joueur est compté comme un deuxième carton jaune uniquement si cette convention est identifiée et disponible dans la source.
- Les cartons aux entraîneurs, remplaçants, membres du staff et banc sont exclus de la cible principale.
- Les doublons d'événements doivent être dédupliqués sur une clé documentée, jamais au moyen d'une suppression manuelle non tracée.

Une analyse de sensibilité doit être prévue si la source ne permet pas de distinguer de façon fiable deuxième jaune, carton rouge direct et carton de banc.

---

## 4. Modèle de données et contrats d'artefacts

### 4.1 Arborescence recommandée

```text
data/
  raw/{competition}/{season}/
  canonical/{competition}/{season}/
  snapshots/{competition}/{season}/
  predictions/{run_id}/
  evaluation/{run_id}/
configs/
logs/
reports/
tests/
experiment_manifest.json
```

Les réponses brutes Laya sont conservées dans `predictions/{run_id}/raw/` et référencées dans la base par chemin et hash.

### 4.2 Tables minimales

```sql
matches (
  match_id TEXT PRIMARY KEY,
  source_match_id TEXT NOT NULL,
  competition_id TEXT NOT NULL,
  season TEXT NOT NULL,
  date_utc TEXT NOT NULL,
  kickoff_timestamp TEXT NOT NULL,
  home_team_id TEXT NOT NULL,
  away_team_id TEXT NOT NULL,
  home_goals INTEGER NOT NULL,
  away_goals INTEGER NOT NULL,
  total_corners INTEGER,
  total_yellow_cards INTEGER,
  total_red_cards INTEGER,
  status TEXT NOT NULL,
  source_hash TEXT NOT NULL
);

match_events (
  event_id TEXT PRIMARY KEY,
  match_id TEXT NOT NULL,
  elapsed_seconds INTEGER NOT NULL,
  period INTEGER NOT NULL,
  event_type TEXT NOT NULL,
  team_id TEXT,
  player_id TEXT,
  detail TEXT,
  source_event_id TEXT,
  source_hash TEXT NOT NULL
);

match_statistics (
  stat_id TEXT PRIMARY KEY,
  match_id TEXT NOT NULL,
  available_timestamp TEXT NOT NULL,
  elapsed_seconds INTEGER NOT NULL,
  team_id TEXT NOT NULL,
  shots INTEGER,
  shots_on_target INTEGER,
  corners INTEGER,
  yellow_cards INTEGER,
  red_cards INTEGER,
  possession REAL,
  xg REAL,
  source_hash TEXT NOT NULL
);

pre_match_context (
  pre_match_id TEXT PRIMARY KEY,
  match_id TEXT NOT NULL,
  team_id TEXT NOT NULL,
  cutoff_timestamp TEXT NOT NULL,
  feature_version TEXT NOT NULL,
  form_last_5 TEXT,
  form_last_10 TEXT,
  goals_scored_avg REAL,
  goals_conceded_avg REAL,
  head_to_head TEXT,
  ranking_before REAL,
  xg_for_avg REAL,
  xg_against_avg REAL,
  injuries TEXT,
  suspensions TEXT,
  lineup TEXT,
  pre_match_odds TEXT,
  source_match_ids TEXT NOT NULL
);

match_snapshots (
  snapshot_id TEXT PRIMARY KEY,
  match_id TEXT NOT NULL,
  cutoff_seconds INTEGER NOT NULL,
  cutoff_timestamp TEXT NOT NULL,
  snapshot_type TEXT NOT NULL,
  information_tier TEXT NOT NULL,
  state_json TEXT NOT NULL,
  state_hash TEXT NOT NULL,
  validation_status TEXT NOT NULL
);

laya_predictions (
  prediction_id TEXT PRIMARY KEY,
  snapshot_id TEXT NOT NULL,
  model_version TEXT NOT NULL,
  run_id TEXT NOT NULL,
  raw_response_path TEXT NOT NULL,
  raw_response_hash TEXT NOT NULL,
  parsed_response TEXT,
  probability_1 TEXT,
  probability_x TEXT,
  probability_2 TEXT,
  expected_goals REAL,
  expected_corners REAL,
  expected_yellow_cards REAL,
  model_confidence REAL,
  latency_ms REAL,
  status TEXT NOT NULL,
  error_code TEXT
);

evaluation (
  evaluation_id TEXT PRIMARY KEY,
  prediction_id TEXT NOT NULL,
  actual_result TEXT NOT NULL,
  actual_home_goals INTEGER NOT NULL,
  actual_away_goals INTEGER NOT NULL,
  actual_total_corners INTEGER NOT NULL,
  actual_total_yellow_cards INTEGER NOT NULL,
  log_loss_1x2 REAL,
  brier_1x2 REAL,
  score_bucket_log_loss REAL,
  rps_1x2 REAL,
  mae_goals REAL,
  mae_corners REAL,
  mae_yellow_cards REAL,
  created_at TEXT NOT NULL
);
```

### 4.3 Identifiants et idempotence

Utiliser des identifiants déterministes :

- `team_id = SHA256(competition_id + ':' + canonical_team_name)` ;
- `match_id = SHA256(competition_id + ':' + season + ':' + kickoff_timestamp + ':' + home_team_id + ':' + away_team_id)` ;
- `snapshot_id = match_id + ':' + cutoff_seconds + ':' + information_tier + ':' + variant_id`.

Un agent doit pouvoir relancer une étape sans créer un second match, un second snapshot ou une seconde prédiction pour le même `run_id`.

---

## 5. Construction point-in-time et prévention des fuites

### 5.1 Temps de référence

Pour chaque match, définir :

- `T_kickoff` : heure officielle du coup d'envoi ;
- `T_pre_match_cutoff` : `T_kickoff`, sauf si l'étude inclut explicitement compositions ou cotes disponibles à une heure antérieure ;
- `cutoff_seconds` : temps écoulé de jeu utilisé par le snapshot ;
- `cutoff_timestamp` : timestamp réel correspondant au cutoff.

Les minutes affichées par une source ne suffisent pas toujours. Utiliser `elapsed_seconds` lorsque disponible, et documenter le traitement des arrêts de jeu.

### 5.2 Bloc pré-match

Toutes les variables pré-match d'un match `M` doivent dépendre uniquement de données dont la date de disponibilité est strictement antérieure à `T_pre_match_cutoff`.

Calculer les agrégats avec une vue temporelle :

```sql
WHERE available_timestamp < :pre_match_cutoff
  AND match_id <> :current_match_id
```

Le filtre ne doit pas être remplacé par un filtre sur la saison entière ou par un classement final.

Pour chaque feature, stocker les `source_match_ids` utilisés. Une validation vérifie que chacun possède `available_timestamp < T_pre_match_cutoff`.

### 5.3 Snapshots live

À un cutoff `t`, inclure uniquement les observations dont la disponibilité est antérieure ou égale au cutoff :

```sql
WHERE match_id = :match_id
  AND available_timestamp <= :cutoff_timestamp
  AND elapsed_seconds <= :cutoff_seconds
```

Une statistique publiée uniquement à la fin du match ne doit jamais être utilisée comme statistique live, même si elle contient une colonne `minute`.

### 5.4 Champs interdits

Ne jamais inclure dans `state_json` :

- score final ;
- buts finaux par équipe ;
- corners finaux ;
- cartons finaux ;
- résultat réel ;
- événement postérieur au cutoff ;
- statistiques dites `full_time`, `final`, `total_match` ou équivalentes ;
- identifiants ou textes révélant la cible ;
- nom d'un fichier de résultat ou d'évaluation ;
- sorties d'une précédente prédiction Laya pour le même match.

Le test de fuite doit inspecter les clés, les valeurs, les métadonnées, le texte sérialisé et les chemins référencés.

### 5.5 Tests anti-fuite obligatoires

Chaque snapshot doit passer les tests suivants :

```python
def test_no_future_events(snapshot, events):
    cutoff = snapshot["cutoff_seconds"]
    future = [e for e in events
              if e["match_id"] == snapshot["match_id"]
              and e["elapsed_seconds"] > cutoff]
    assert not future

def test_no_final_fields(snapshot):
    forbidden = (
        "final_score", "final_goals", "final_corners",
        "final_yellow_cards", "actual_result", "full_time"
    )
    serialized = json.dumps(snapshot["state"], sort_keys=True).lower()
    assert not any(key in serialized for key in forbidden)

def test_pre_match_sources_before_cutoff(snapshot, contexts, matches):
    cutoff = snapshot["state"]["metadata"]["pre_match_cutoff_timestamp"]
    used_ids = set(snapshot["state"]["metadata"]["pre_match_source_match_ids"])
    for match in matches:
        if match["match_id"] in used_ids:
            assert match["available_timestamp"] < cutoff
```

Ajouter un test négatif : injecter artificiellement un événement futur et vérifier que le validateur échoue. Les tests doivent être exécutés sur 100 % des snapshots, pas seulement sur l'échantillon audité manuellement.

### 5.6 Audit manuel

Auditer au moins 5 % des snapshots, stratifiés par compétition, saison, cutoff et type d'événement. L'audit vérifie la cohérence entre source brute, événement canonique et état transmis à Laya. Les auditeurs consignent leur décision et leur justification.

---

## 6. Plan de snapshots et niveaux d'information

### 6.1 Snapshots fixes

Créer, si le match est encore en jeu à l'instant correspondant :

- `pre_match` ;
- 15 minutes ;
- 30 minutes ;
- 45 minutes ;
- 60 minutes ;
- 75 minutes ;
- 85 minutes.

Le snapshot à 45 minutes représente l'état à la fin de la première période avant les événements de la pause, sauf décision contraire documentée.

### 6.2 Snapshots événementiels

Créer un snapshot immédiatement après chaque :

- but ;
- carton rouge ;
- penalty accordé ou tiré ;
- remplacement.

Le type d'événement, son timestamp et son identifiant sont enregistrés dans les métadonnées. Si plusieurs événements ont le même timestamp, créer un snapshot après l'ordre source documenté et une version agrégée de contrôle.

### 6.3 Tiers d'information

Pour l'étude d'ablation, définir avant l'analyse :

- **Tier A — pré-match :** forme, classement disponible, historiques, cotes autorisées et contexte d'avant-match ;
- **Tier B — live minimal :** Tier A + score, cartons, corners, expulsions et événements disponibles ;
- **Tier C — live complet :** Tier B + tirs, tirs cadrés, possession et xG lorsque ces variables étaient réellement disponibles au cutoff.

Les tiers sont des états différents d'un même match et ne doivent pas être comparés comme des observations indépendantes dans les intervalles de confiance.

---

## 7. État transmis à Laya

### 7.1 Sérialisation canonique

Le JSON doit être déterministe : clés triées, nombres avec précision fixée, valeurs manquantes représentées par `null`, pas de texte libre non contrôlé et encodage UTF-8.

Exemple :

```json
{
  "metadata": {
    "competition": "Premier League",
    "season": "2023-2024",
    "home_team": "Team A",
    "away_team": "Team B",
    "cutoff_seconds": 3600,
    "cutoff_timestamp": "2024-01-15T16:00:00Z",
    "information_tier": "C"
  },
  "pre_match": {
    "home": {},
    "away": {}
  },
  "live": {
    "score": {"home": 1, "away": 0},
    "corners": {"home": 4, "away": 3},
    "yellow_cards": {"home": 1, "away": 2},
    "red_cards": {"home": 0, "away": 0},
    "shots": {"home": 8, "away": 5},
    "shots_on_target": {"home": 3, "away": 2},
    "possession": {"home": 55.0, "away": 45.0},
    "xg": {"home": 1.2, "away": 0.8}
  }
}
```

Le champ `metadata.cutoff_timestamp` sert à auditer le snapshot. Il ne doit pas encoder indirectement le résultat, par exemple via un nom de fichier ou un identifiant contenant une cible.

### 7.2 Gestion des données manquantes

Ne jamais remplacer une variable live manquante par une statistique finale ou par une valeur calculée avec le résultat du match.

Valeurs acceptées :

- `null` si le modèle et le SDK l'acceptent ;
- omission contrôlée, documentée et identique entre Laya et baseline ;
- catégorie `unavailable` uniquement si elle est prévue avant la collecte.

Le taux de données manquantes est rapporté par variable, source, compétition, saison et cutoff.

---

## 8. Tâches typées et support des cibles

### 8.1 Résultat 1X2

Le 1X2 est dérivé de la distribution jointe de score :

```text
P(1) = somme P(h, a) pour h > a
P(X) = somme P(h, a) pour h = a
P(2) = somme P(h, a) pour h < a
```

Le score réel de 90 minutes plus arrêts de jeu est utilisé, sans prolongation ni tirs au but.

### 8.2 Score regroupé : correction de la catégorie `other`

La grille initiale ne doit pas être décrite comme une distribution du score exact si elle contient une classe `other`.

La tâche primaire recommandée est une distribution **score bucket** avec :

```text
0-0, 0-1, 0-2, 0-3,
1-0, 1-1, 1-2, 1-3,
2-0, 2-1, 2-2, 2-3,
3-0, 3-1, 3-2, 3-3,
other
```

Tout score dont au moins une composante est supérieure à 3 est mappé vers `other`. La log loss et la calibration portent alors sur ces 17 catégories, et non sur le score exact.

Pour analyser les buts avec davantage de résolution, ajouter deux tâches marginales séparées :

- buts domicile : `0` à `7`, puis `8+` ;
- buts extérieur : `0` à `7`, puis `8+`.

Ces marginales ne doivent pas être recombinées en une distribution jointe sans méthode explicitement validée.

### 8.3 Corners

Utiliser les niveaux `0` à `20` plus `21+` lorsque le type `score` accepte une queue ordonnée. Si le SDK ne permet pas une classe de queue, utiliser une cible censurée `min(total_corners, 20)` et ne pas présenter l'espérance comme une espérance non censurée.

### 8.4 Cartons jaunes

Utiliser les niveaux `0` à `12` plus `13+`, avec la même règle de queue. Le seuil peut être augmenté avant l'expérience si une analyse descriptive montre une fréquence de queue trop élevée ; il ne doit pas être choisi après comparaison des résultats.

### 8.5 Définition des questions

```python
QUESTIONS_V1 = {
    "score_bucket": {
        "type": "choice",
        "instructions": "What is the final score category of this football match?",
        "criteria": SCORE_BUCKET_CRITERIA,
    },
    "total_corners": {
        "type": "score",
        "instructions": "What will be the total number of corners in the match?",
        "criteria": [str(i) for i in range(21)] + ["21+"],
    },
    "total_yellow_cards": {
        "type": "score",
        "instructions": "What will be the total number of yellow cards in the match?",
        "criteria": [str(i) for i in range(13)] + ["13+"],
    },
}
```

Les noms, l'ordre des catégories et la formulation exacte sont versionnés. Toute modification crée une nouvelle version de tâche.

### 8.6 Validateur de réponse

Avant insertion :

1. vérifier que la réponse est du JSON valide ;
2. vérifier les clés attendues et uniquement les clés documentées ;
3. vérifier que chaque probabilité est finie, comprise entre 0 et 1 ;
4. vérifier que la somme vaut 1 à `1e-6` près ;
5. vérifier l'absence de catégorie manquante ou dupliquée ;
6. vérifier la cohérence de la valeur espérée avec la convention de queue ;
7. conserver le texte brut avant toute transformation.

Une somme hors tolérance produit `INVALID_PROBABILITY_SUM`. Il est interdit de renormaliser silencieusement. Une éventuelle normalisation explicitement autorisée doit être séparée, versionnée et comptée comme une variante d'analyse.

---

## 9. Exécution de l'agent Laya

### 9.1 Procédure

Pour chaque snapshot valide :

1. charger `state_json` ;
2. vérifier son hash et son statut anti-fuite ;
3. sérialiser l'état de façon canonique ;
4. exécuter la version de questions prévue ;
5. appeler le routeur avec le checkpoint déclaré ;
6. écrire la réponse brute immédiatement ;
7. valider puis parser ;
8. dériver 1X2 et les statistiques de comptage ;
9. enregistrer latence, statut, erreur éventuelle et hash de la réponse.

### 9.2 Déterminisme

Réaliser un audit de répétition sur un échantillon stratifié d'au moins 10 % des snapshots, avec `k = 5` requêtes identiques.

- Si les sorties sont identiques, une requête suffit pour la production et l'audit est conservé.
- Si elles diffèrent, utiliser `k = 5` pour tous les snapshots du protocole principal, ou figer et justifier une règle d'agrégation avant le test.
- Ne jamais moyenner une distribution sans conserver les cinq sorties individuelles.

Rapporter la variance inter-appels, la fréquence de changement de décision et la variation de log loss.

### 9.3 Erreurs et reprises

Les erreurs réseau peuvent être retentées avec backoff exponentiel borné. Une reprise ne doit pas remplacer la réponse d'origine : chaque tentative est journalisée.

Les erreurs de parsing, de schéma ou de fuite sont des erreurs de validité et ne doivent pas être corrigées par une reprise automatique sans diagnostic.

Codes minimaux :

```text
OK
NETWORK_RETRY_EXHAUSTED
INVALID_JSON
INVALID_SCHEMA
INVALID_PROBABILITY
INVALID_PROBABILITY_SUM
MISSING_CATEGORY
LEAKAGE_DETECTED
CONTEXT_TOO_LONG
SDK_ERROR
```

### 9.4 Confiance

Stocker la confiance renvoyée par Laya, mais évaluer séparément :

- calibration des probabilités ;
- calibration de la confiance contre la correction de la décision la plus probable ;
- relation entre confiance et log loss.

Une forte confiance n'est pas une preuve de justesse.

---

## 10. Baselines équitables

Toutes les baselines sont entraînées ou calculées avec des données disponibles au même cutoff.

### 10.1 Baselines minimales

- **Uniforme :** distribution uniforme sur les catégories ; contrôle de référence.
- **Fréquence historique :** fréquence observée dans la fenêtre d'entraînement, par compétition et éventuellement par saison.
- **Score actuel :** conserver le score actuel comme score final ; baseline volontairement naïve et non probabiliste, à convertir en distribution avec une règle pré-enregistrée si nécessaire.
- **Persistance des comptages :** comptage actuel + moyenne historique du reste, avec définition précise du reste.

Une baseline qui produit une valeur ponctuelle ne doit pas être comparée à une distribution sans méthode de conversion documentée.

### 10.2 Modèles statistiques

Prévoir au minimum :

- Poisson indépendant ou bivarié pour les buts ;
- modèle Dixon-Coles ou équivalent si justifié ;
- Poisson ou binomial négatif pour corners et cartons ;
- régression logistique multinomiale pour 1X2 ;
- modèle tabulaire optionnel, par exemple gradient boosting, uniquement avec split temporel.

Les hyperparamètres sont fixés sur validation. Le test final n'est jamais utilisé pour les choisir.

### 10.3 Cotes de bookmakers

Les cotes pré-match sont une baseline forte uniquement au snapshot pré-match, sauf si des cotes live timestampées sont disponibles et intégrées de façon identique.

Convertir les cotes en probabilités implicites, puis retirer la marge selon une méthode définie avant l'analyse. Ne pas utiliser une cote publiée après le cutoff.

### 10.4 Comparaison équitable

Chaque baseline doit recevoir un tableau de features `information_tier` équivalent à celui transmis à Laya. Une baseline qui bénéficie de variables indisponibles à Laya est exclue de la comparaison principale et présentée en analyse auxiliaire.

---

## 11. Découpage, validation et puissance

### 11.1 Découpage temporel

Ne pas effectuer de split aléatoire au niveau des snapshots.

Protocole recommandé :

- entraînement : périodes les plus anciennes ;
- validation : période immédiatement suivante ;
- test final : période la plus récente, jamais consultée pour les choix de modèle.

Si trois saisons seulement sont disponibles, utiliser un schéma rolling-origin documenté et un holdout temporel final. Les matchs d'un même jour doivent rester dans le même bloc si la disponibilité des features peut créer une dépendance.

### 11.2 Dépendance des observations

Les snapshots d'un match partagent le même résultat final. Les observations événementielles sont encore plus dépendantes. Les métriques par snapshot sont utiles descriptivement, mais les erreurs standards et intervalles doivent être groupés par `match_id`.

### 11.3 Analyse de puissance

Avant la collecte finale, définir :

- métrique principale par cible ;
- différence minimale d'intérêt ;
- taux d'exclusion attendu ;
- nombre de matchs nécessaires ;
- nombre de compétitions et saisons ;
- nombre maximal de tests confirmatoires.

Si la puissance est insuffisante, rapporter une estimation imprécise et ne pas conclure à l'équivalence sur la base d'un résultat non significatif.

### 11.4 Critères de qualité avant analyse

Le test final est bloqué si :

- plus de 5 % des snapshots contiennent une fuite ;
- plus de 10 % des matchs d'une strate obligatoire sont manquants ;
- le taux de réponses Laya invalides dépasse 5 % sans analyse de sensibilité ;
- un checkpoint ou une tâche n'est pas entièrement versionné ;
- la provenance d'une cible ou d'une feature ne peut pas être auditée.

Ces seuils peuvent être modifiés uniquement dans le manifeste pré-enregistré.
## 12. Métriques d'évaluation

### 12.1 Classification 1X2

Calculer :

- log loss multiclass, avec plancher `epsilon = 1e-15` ;
- Brier score multiclass ;
- accuracy de la classe la plus probable ;
- RPS, car 1X2 est ordonné ;
- ECE avec bins et méthode annoncés ;
- courbe de fiabilité ;
- log loss par cutoff, compétition, saison et tier.

L'AUC n'est pas une métrique principale pour une cible multiclass ordonnée. Si elle est fournie, elle doit être présentée comme analyse auxiliaire avec méthode one-vs-rest explicitée.

### 12.2 Score bucket

Calculer :

- log loss sur les 17 catégories ;
- Brier multiclass ;
- RPS si un ordre cohérent des catégories est défini ;
- accuracy du bucket le plus probable ;
- calibration par catégorie fréquente et pour `other`.

Ne pas appeler cette métrique « log loss du score exact ».

### 12.3 Comptages

Pour corners et cartons :

- MAE de la valeur attendue, uniquement si la convention de queue est compatible ;
- RMSE ;
- log score discret ;
- CRPS discret ;
- déviance de Poisson ou binomiale négative quand elle est applicable ;
- couverture des intervalles prédictifs à 50 %, 80 % et 95 % ;
- largeur moyenne de ces intervalles ;
- PIT randomisé pour variables discrètes ;
- taux de masse dans la queue `21+` ou `13+`.

Si une queue est censurée, rapporter séparément les métriques sur la cible censurée et la limitation d'interprétation de la valeur attendue.

### 12.4 Calibration

Pour chaque distribution, rapporter :

- ECE et nombre de bins ;
- maximum calibration error ;
- courbe de fiabilité ;
- histogramme PIT randomisé pour les comptages ;
- couverture empirique ;
- décomposition du Brier si elle est implémentée.

L'ECE dépend de la méthode de binning. La méthode doit être figée et une analyse de sensibilité par quantiles peut être ajoutée.

### 12.5 Intervalles et tests

Utiliser un bootstrap stratifié et groupé par match, avec au moins 2 000 réplications si le budget le permet.

Pour comparer deux modèles :

- calculer la différence de contribution par match ;
- utiliser un intervalle bootstrap groupé ;
- fournir la différence moyenne, l'IC 95 % et une taille d'effet ;
- appliquer Holm-Bonferroni aux familles de tests pré-définies.

Un test non significatif ne prouve pas l'égalité des modèles.

---

## 13. Robustesse et réactions aux événements

### 13.1 Paraphrases

Créer un petit ensemble versionné de formulations sémantiquement équivalentes. Le contenu de l'état et les catégories restent identiques.

Mesurer :

- variation absolue moyenne des probabilités ;
- distance de Jensen-Shannon ;
- distance de variation totale ;
- variation de l'espérance ;
- taux de changement de classe la plus probable ;
- variation de log loss.

Une seule décision 1X2 ne suffit pas à mesurer la robustesse d'une distribution.

### 13.2 Réordonnancement et format

Tester séparément :

- ordre des champs JSON ;
- noms des champs autorisés ;
- représentation JSON compacte ou indentée ;
- français contre anglais, uniquement si le modèle multilingue est évalué ;
- présence d'un dictionnaire descriptif fixe.

Chaque variante doit conserver le même contenu sémantique et le même budget de contexte.

### 13.3 Réaction événementielle

Pour chaque événement admissible, comparer les snapshots avant/après dans une fenêtre temporelle définie à l'avance.

Exemples de direction attendue, sans interprétation causale automatique :

- but domicile : hausse moyenne de `P(1)` ;
- but extérieur : hausse moyenne de `P(2)` ;
- carton rouge domicile : baisse moyenne de `P(1)` et hausse possible de `P(2)` ;
- penalty : effet cohérent avec l'équipe bénéficiaire si l'issue du penalty n'est pas postérieure au cutoff.

Mesurer aussi la réaction sur les distributions de corners et cartons, sans supposer qu'un événement doit améliorer tous les objectifs.

### 13.4 Snapshots quasi identiques

Identifier les paires de snapshots dont l'état diffère peu mais dont l'heure ou l'événement diffère. Rechercher :

- oscillations non justifiées ;
- changements de classe sans nouvelle information ;
- probabilités excessivement concentrées ;
- incohérences entre score actuel et distribution finale.

Cette analyse est descriptive et ne remplace pas l'évaluation hors échantillon.

---

## 14. Architecture des agents IA

Les agents ne communiquent pas directement. Ils lisent et écrivent des artefacts versionnés, avec un statut et un hash.

### 14.1 Agent Orchestrateur

Responsabilités :

- créer `experiment_manifest.json` ;
- valider les versions et les paramètres ;
- exécuter les agents dans l'ordre ;
- vérifier les préconditions et postconditions ;
- arrêter le pipeline sur erreur bloquante ;
- produire un journal de run.

### 14.2 Agent Collecteur

Entrées : manifest, sources autorisées, paramètres de compétition.

Sorties : réponses brutes, journaux d'appels, hashes, rapport de couverture.

Règles : pas de transformation, retries bornés, aucune déduction à partir d'une réponse partielle.

### 14.3 Agent Nettoyeur

Entrées : données brutes immuables.

Sorties : données canoniques, `cleaning_report.json`, exclusions motivées.

Contrôles : identifiants, doublons, horaires, score, événements, conventions de cartons et corners.

### 14.4 Agent Pré-match

Entrées : données canoniques antérieures à chaque cutoff.

Sorties : `pre_match_context`, liste des matchs sources par feature, `pre_match_validation.json`.

Blocage : aucune feature ne passe si son historique contient une date future ou le match courant.

### 14.5 Agent Snapshot

Entrées : match canonique, contexte pré-match, règles de cutoff.

Sorties : snapshots fixes et événementiels, hashes d'état, `snapshot_validation.json`.

Blocage : tous les tests anti-fuite doivent réussir avant publication des snapshots.

### 14.6 Agent Laya

Entrées : snapshots validés, configuration de questions, checkpoint.

Sorties : réponses brutes, prédictions normalisées, latences, erreurs, audit de répétition.

Blocage : réponse invalide isolée, jamais remplacée par une réponse modifiée.

### 14.7 Agent Baselines

Entrées : mêmes snapshots et split temporel.

Sorties : distributions des baselines, paramètres entraînés, métriques d'ajustement.

Blocage : aucun entraînement sur le test final.

### 14.8 Agent Évaluateur

Entrées : prédictions valides, cibles finales, manifeste figé.

Sorties : contribution par prédiction, agrégats, bootstrap, calibration, comparaison par modèle.

Blocage : aucune agrégation sans rapport du dénominateur et du taux d'invalidité.

### 14.9 Agent Analyste

Entrées : rapports d'évaluation, manifestes, journaux, exclusions.

Sorties : rapport final en Markdown et PDF, tableau des limites, annexes reproductibles.

Règle : séparer explicitement résultats confirmatoires, analyses exploratoires et hypothèses.

---

## 15. Contrat de communication et journalisation

Chaque artefact contient au minimum :

```json
{
  "schema_version": "1.0.0",
  "experiment_id": "exp_2026_001",
  "run_id": "run_001",
  "producer": "snapshot_agent",
  "created_at": "2026-09-25T12:00:00Z",
  "input_hashes": [],
  "output_hash": "sha256:...",
  "status": "validated",
  "record_count": 0,
  "warnings": [],
  "errors": []
}
```

Journaux obligatoires :

- `logs/orchestrator.log` ;
- `logs/collector.log` ;
- `logs/cleaner.log` ;
- `logs/pre_match.log` ;
- `logs/snapshot.log` ;
- `logs/laya.log` ;
- `logs/baselines.log` ;
- `logs/evaluator.log` ;
- `logs/analyst.log` ;
- `logs/errors.log`.

Chaque ligne de journal comprend `timestamp`, `agent`, `run_id`, `entity_id`, `action`, `status` et un message court sans donnée personnelle.

---

## 16. Ordre d'exécution et commandes de référence

Les commandes réelles doivent être adaptées au dépôt, mais l'ordre logique est fixe :

```bash
python -m src.storage.database init
python -m agents.collector --config configs/experiment.yaml
python -m agents.cleaner --run-id RUN_ID
python -m agents.pre_match --run-id RUN_ID
python -m agents.snapshot --run-id RUN_ID
python -m agents.laya --run-id RUN_ID --task-version v1
python -m agents.baselines --run-id RUN_ID
python -m agents.evaluator --run-id RUN_ID
python -m agents.analyst --run-id RUN_ID
```

Avant chaque étape : vérifier les artefacts prérequis. Après chaque étape : écrire un manifeste de sortie et un statut `validated`, `warning` ou `blocked`.

---

## 17. Reproductibilité

Conserver :

- code source et commit ou archive versionnée ;
- fichier de dépendances avec versions exactes ;
- version Python ;
- manifest complet de l'expérience ;
- seed et configuration de chaque modèle ;
- version exacte de Laya et hash du checkpoint ;
- hashes SHA-256 des données brutes et canoniques ;
- questions et critères exacts ;
- réponses Laya brutes ;
- scripts de génération des snapshots ;
- scripts et paramètres des métriques ;
- exclusions et erreurs ;
- rapport de taille d'échantillon ;
- date et timezone de tous les timestamps.

Une reproduction doit pouvoir repartir des fichiers bruts sans appeler de nouveau l'API externe, sauf étape explicitement marquée non reproductible.

---

## 18. Limites, éthique et gouvernance

- Les données sportives publiques peuvent être incomplètes, corrigées après publication ou soumises à licence.
- La qualité apparente de Laya peut refléter des biais de couverture des compétitions ou des sources.
- Les événements et statistiques live peuvent être publiés avec retard ; la disponibilité réelle doit être modélisée.
- Les snapshots d'un même match ne constituent pas des observations indépendantes.
- Une catégorie `other` ou une queue censurée limite l'interprétation du score ou de l'espérance.
- Les effets après événement ne sont pas des effets causaux.
- Les résultats ne doivent pas être présentés comme un conseil de pari ni comme une garantie de résultat.
- Aucune donnée personnelle sensible n'est nécessaire ; les identifiants de joueurs doivent être pseudonymisés si conservés.
- Les erreurs de modèle et les données manquantes doivent être rapportées, pas masquées par une imputation opportuniste.

---

## 19. Livrables et critères d'acceptation

### 19.1 Livrables

- dataset brut documenté ;
- dataset canonique et rapport de nettoyage ;
- base SQLite ou équivalent ;
- contexte pré-match validé ;
- snapshots et rapport anti-fuite ;
- réponses Laya brutes et prédictions normalisées ;
- prédictions des baselines ;
- table d'évaluation ;
- métriques par snapshot, compétition et saison ;
- bootstrap et courbes de calibration ;
- rapport final Markdown et PDF ;
- dictionnaire de données ;
- manifeste et changelog ;
- instructions de reproduction.

### 19.2 Critères d'acceptation

Le protocole est considéré exécutable si :

1. un run complet peut être lancé depuis un manifeste ;
2. tous les artefacts ont un hash et un producteur ;
3. 100 % des snapshots passent les tests anti-fuite ;
4. toutes les réponses sont classées valides ou invalides avec un code ;
5. le dénominateur de chaque métrique est publié ;
6. les baselines utilisent un split temporel équivalent ;
7. les intervalles sont groupés par match ;
8. les limitations des catégories `other` et des queues sont visibles dans le rapport ;
9. les résultats du test final ne servent pas à modifier le protocole ;
10. un tiers peut reproduire au moins les métriques principales à partir des artefacts conservés.

---

## 20. Structure du rapport final

Le rapport final doit suivre cette structure :

1. Résumé exécutif ;
2. Questions et hypothèses pré-enregistrées ;
3. Sources, périmètre et exclusions ;
4. Définition point-in-time et contrôles anti-fuite ;
5. Version de Laya et tâches typées ;
6. Baselines et découpage temporel ;
7. Métriques et plan statistique ;
8. Résultats globaux ;
9. Résultats par cutoff, compétition et tier ;
10. Calibration ;
11. Robustesse et réactions aux événements ;
12. Analyse des erreurs ;
13. Résultats confirmatoires ;
14. Analyses exploratoires ;
15. Limites ;
16. Conclusion ;
17. Annexes de reproductibilité.

Chaque tableau de résultat indique : modèle, cible, cutoff, nombre de matchs, nombre de snapshots, nombre de réponses valides, métrique, intervalle de confiance et méthode de bootstrap.

---

## 21. Checklist opérationnelle par agent

### Collecteur

- [ ] source et licence documentées ;
- [ ] appels et erreurs journalisés ;
- [ ] réponses brutes immuables ;
- [ ] hash calculé ;
- [ ] couverture par compétition et saison publiée.

### Nettoyeur

- [ ] identifiants déterministes ;
- [ ] doublons traités et justifiés ;
- [ ] conventions buts, corners et cartons appliquées ;
- [ ] incohérences isolées ;
- [ ] aucune feature dérivée du résultat injectée dans les données live.

### Pré-match

- [ ] cutoff strict enregistré ;
- [ ] matchs sources listés ;
- [ ] toutes les dates antérieures au cutoff ;
- [ ] classement et forme point-in-time ;
- [ ] absence de statistiques de fin de saison.

### Snapshot

- [ ] cutoffs fixes créés selon la règle ;
- [ ] événements admissibles inclus jusqu'au cutoff ;
- [ ] événements futurs absents ;
- [ ] champs finaux absents ;
- [ ] tiers d'information correctement étiquetés ;
- [ ] hash d'état calculé.

### Agent Laya

- [ ] SDK et checkpoint versionnés ;
- [ ] tâche versionnée ;
- [ ] réponse brute sauvegardée avant parsing ;
- [ ] probabilités validées ;
- [ ] invalidités journalisées ;
- [ ] déterminisme audité ;
- [ ] aucune correction manuelle silencieuse.

### Évaluateur

- [ ] labels finaux joints uniquement après prédiction ;
- [ ] métriques adaptées aux queues ;
- [ ] bootstrap groupé par match ;
- [ ] corrections multiples appliquées ;
- [ ] dénominateurs et exclusions publiés.

### Analyste

- [ ] confirmatoire séparé d'exploratoire ;
- [ ] observations séparées des hypothèses ;
- [ ] incertitude rapportée ;
- [ ] limites explicites ;
- [ ] conclusion limitée au périmètre observé ;
- [ ] rapport reproductible à partir des artefacts.

---

## Annexe A — Exemple de manifeste minimal

```json
{
  "experiment_id": "laya-football-001",
  "protocol_version": "2.0.0",
  "competitions": ["EPL", "LaLiga", "SerieA", "Bundesliga", "Ligue1"],
  "seasons": ["2021-2022", "2022-2023", "2023-2024"],
  "primary_source": "SOURCE_NAME",
  "secondary_source": "SOURCE_NAME",
  "cutoffs_seconds": [0, 900, 1800, 2700, 3600, 4500, 5100],
  "information_tiers": ["A", "B", "C"],
  "score_bucket_cap": 3,
  "corners_tail": "21+",
  "yellow_cards_tail": "13+",
  "model": {
    "package": "laya",
    "version": "PINNED_VERSION",
    "checkpoint": "PINNED_CHECKPOINT",
    "router_mode": "multilingual"
  },
  "bootstrap_replicates": 2000,
  "alpha": 0.05,
  "seed": 20260925,
  "primary_metrics": {
    "1x2": "log_loss",
    "score_bucket": "log_loss",
    "corners": "crps",
    "yellow_cards": "crps"
  }
}
```

---

## Annexe B — Décisions à figer avant le test final

Les points suivants doivent recevoir une valeur dans le manifeste ; aucune valeur par défaut implicite n'est autorisée :

- source principale et source secondaire ;
- saisons et compétitions ;
- timezone et définition du kickoff ;
- disponibilité réelle des statistiques ;
- convention du deuxième carton jaune ;
- traitement des événements de même timestamp ;
- seuils de queue ;
- définition exacte des tiers A, B et C ;
- wording et ordre des critères ;
- checkpoint Laya ;
- nombre de répétitions ;
- split temporel ;
- métriques principales ;
- nombre de réplications bootstrap ;
- familles de tests pour Holm-Bonferroni ;
- critères de blocage et de reprise ;
- règle de gestion des données manquantes.

Une décision prise après inspection du test final doit être marquée comme analyse post hoc et exclue des conclusions confirmatoires.
