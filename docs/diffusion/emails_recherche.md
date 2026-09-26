# Emails de contact chercheurs — template (anglais)

**Objet du fichier :** modèle d'email pour contacter des chercheurs et groupes de recherche afin de faire connaître le protocole et d'inviter des retours critiques pendant la fenêtre de pré-enregistrement (avant l'exécution de l'étude).

**Placeholders restants :** [RESEARCHER NAME] (nom du destinataire), [EMAIL] (adresse personnelle d'expédition), [PREPRINT LINK — arXiv], [ONE SPECIFIC POINT]. DOI, nom d'auteur et URL du dépôt sont en place.

---

## À qui envoyer

- **MathSport International** — communauté « mathématiques et sport » (modèles de buts, Dixon-Coles, calibration) : membres actifs sur la modélisation des scores et les métriques probabilistes.
- **SSAC / MIT Sloan Sports Analytics Conference** — chercheurs et praticiens en sports analytics intéressés par les méthodes d'évaluation et les approches temps réel.
- **Groupes de recherche en forecasting / évaluation probabiliste** — équipes travaillant sur les proper scoring rules, la calibration des prédictions et l'évaluation des prédictions LLM (ex. groupes autour de la prévision agrégée, des tournois de forecasting et de l'évaluation de LLM comme prédicteurs probabilistes).
- **Chercheurs individuels** ayant publié sur : modèles de Poisson/Dixon-Coles appliqués au football, évaluation de la calibration (ECE, PIT randomisé), prédictions in-play, LLM et incertitude.

**Règle de bon usage :** email individuel et personnalisé (mentionner un article ou un thème précis du destinataire dans la première phrase) ; jamais d'envoi de masse.

---

## Template — objet

**EN :** `Preregistered protocol: evaluating an AI decision engine as a live probabilistic forecaster (feedback welcome)`

**Variante courte :** `Feedback requested — preregistered multi-instant evaluation of an AI probabilistic decision engine (football)`

---

## Template — corps (~150 mots)

Dear [RESEARCHER NAME],

I am Steve Djoumessi Mba (Independent Researcher). I have just preregistered the protocol of a study that evaluates a typed AI decision engine ("Laya") as a **live probabilistic forecaster** of football outcomes — 1X2, 17 score buckets, corners, and yellow cards — sampled at seven fixed cutoffs and immediately after goals, red cards, penalties, and substitutions.

The design emphasizes what your work has shown matters: strict point-in-time integrity (automated leakage tests on 100% of snapshots), fair statistical baselines receiving identical information (Poisson, Dixon-Coles, multinomial logit, bookmaker odds), randomized PIT and proper scoring rules, and match-clustered bootstrap with Holm-Bonferroni correction.

The study is preregistered (no results yet, by design), and the code is open source. Before execution, I would greatly value your critique of the protocol, especially [ONE SPECIFIC POINT — e.g., "the tier design" / "the score-bucket target" / "the clustered inference"].

Protocol: https://doi.org/10.17605/OSF.IO/TPSQB — Code: https://github.com/steve-dev-55/laya-football-evaluation — Preprint: [PREPRINT LINK — arXiv]

With best regards,
Steve Djoumessi Mba
Independent Researcher — [EMAIL]

---

## Version française (si nécessaire)

**Objet :** `Protocole pré-enregistré : évaluation d'un moteur de décision IA comme prédicteur probabiliste en temps réel (retours bienvenus)`

**Corps (~130 mots) :** même structure — présentation en une phrase ; le design (point-in-time strict, baselines équitables, PIT randomisé, bootstrap groupé par match, Holm-Bonferroni) ; le statut (pré-enregistré, sans résultats, par design) ; la demande de critique ciblée ; les liens (DOI 10.17605/OSF.IO/TPSQB, dépôt GitHub, preprint) ; signature (Steve Djoumessi Mba, Independent Researcher, [EMAIL]).

---

## Suivi suggéré

1. J+7 : un rappel poli en une phrase si pas de réponse (ne jamais renvoyer l'email complet).
2. Après l'exécution de l'étude (phase 2) : partager les résultats aux personnes ayant répondu, avec remerciement dans les acknowledgements si leur critique a modifié le protocole (avant le gel final).
3. Consigner tous les échanges et dates dans le journal du projet (traçabilité du pré-enregistrement).
