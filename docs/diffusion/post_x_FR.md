# Fil X (Twitter) — Français

**Angle :** pratique — les agents IA comme moteurs de décision probabiliste en temps réel.
**Placeholders à remplacer avant publication :** [OSF DOI] (assigné à l'étape 3 du processus de publication).
**Publier en fil (7 tweets).**

---

**Tweet 1/7 (accroche)**

Peut-on faire confiance à un agent IA comme moteur de probabilités EN DIRECT — et pas juste comme machine à quiz ?

On vient de figer un protocole pré-enregistré pour le vérifier.

17 catégories de score. 7 cutoffs par match. 100 % des snapshots testés anti-fuite.

Le terrain de jeu : le football. La question : générale. 🧵

---

**Tweet 2/7 (le fossé)**

Les benchmarks LLM mesurent la précision sur des questions figées.

Mais un vrai moteur de décision doit faire plus dur : sortir une distribution de probabilités complète à chaque instant d'un processus live — et rester calibré au fil de l'information.

Ça, presque personne ne l'évalue. Alors on l'a construit.

---

**Tweet 3/7 (le design)**

Chaque match est échantillonné à 7 cutoffs fixes (pré-match, 15', 30', 45', 60', 75', 85') ET juste après chaque but, carton rouge, penalty et remplacement.

Trois niveaux d'information : A = pré-match seul, B = +score/événements, C = +tirs, possession, xG.

Même match, information croissante. 📈

---

**Tweet 4/7 (anti-fuite)**

L'ennemi n°1 d'une évaluation live : la contamination post-hoc.

Notre règle centrale : au cutoff t, le modèle ne voit RIEN qui n'était disponible à t. Tests automatiques sur 100 % des snapshots + test négatif par injection + audit manuel ≥ 5 %.

Aucune exception. Échec = pipeline bloqué.

---

**Tweet 5/7 (baselines équitables)**

« L'IA est-elle bonne ? » n'a de sens que face à des baselines équitables.

Chaque baseline reçoit la MÊME information au MÊME cutoff : uniforme, fréquence historique, Poisson, Dixon-Coles, logistique multinomiale, cotes de bookmakers.

Split temporel strict. Bootstrap groupé par match (≥ 2 000 réplications). Holm-Bonferroni.

---

**Tweet 6/7 (pré-enregistrement)**

5 hypothèses pré-enregistrées (H1–H5) : progression temporelle, calibration, réaction aux événements, robustesse aux paraphrases, cibles de comptage.

Pas encore de résultats — c'est voulu. Protocole + code figés AVANT de toucher au jeu de test. Registered report, phase 1.

C'est précisément le but.

---

**Tweet 7/7 (ouverture + CTA)**

Code : MIT. Textes : CC-BY 4.0. Pipeline à 9 agents, artefacts hashés, SQLite, entièrement rejouable.

Repo : https://github.com/steve-dev-55/laya-football-evaluation
Pré-enregistrement : [OSF DOI]

Chercheurs en sports analytics et forecasting : critiquez le protocole maintenant — c'est le meilleur moment.

#SportsAnalytics #LLM #OpenScience #ScienceOuverte

---

*Note : chaque tweet respecte la limite de 280 caractères à la rédaction ; recompter après remplacement du placeholder restant ([OSF DOI] ajoute des caractères — utiliser des liens raccourcis si besoin).*
