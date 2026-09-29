# Post LinkedIn — Français (variante « allusion Jev », v2 sourcée)

**Angle :** Jev (TypeSafe AI) comme référence d'actualité — Laya comme version open source et scientifiquement pré-enregistrée.
**Source Jev :** annonce officielle TypeSafe AI — https://typesafe.ai/blog/introducing-system-one-models-and-jev
**Statut : prêt à publier tel quel (aucun placeholder).**
**Longueur :** ~1 600 caractères visibles (limite LinkedIn 3 000).

---

Vous avez vu l'annonce ? TypeSafe AI vient de lancer **Jev**, premier « System One Model » : des décisions probabilistes calibrées, ~100× plus rapides qu'un LLM, sans génération de texte donc incapables d'halluciner.

La direction est la bonne : les logiciels ont besoin de probabilités fiables, pas de textes.

Mais une question reste ouverte : **comment vérifier qu'un moteur de décision est réellement calibré ?**

Voici **Laya — la version open source de Jev, pour le football.**

Même philosophie que Jev : un état de match en entrée → des distributions de probabilités structurées en sortie (résultat final, 17 catégories de score, corners, cartons) — en temps réel, du coup d'envoi à la 90e minute.

Et une chose que Jev n'a pas : **la vérifiabilité scientifique intégrée.**

✅ Pré-enregistrement OSF (DOI : 10.17605/OSF.IO/TPSQB) — hypothèses, métriques et seuils figés AVANT tout test
✅ Code 100 % open source (MIT) — pipeline de 9 agents, auditable ligne par ligne
✅ Anti-fuite automatique — l'IA ne voit jamais une information postérieure à sa prédiction (vérifié sur 100 % des snapshots)
✅ Baselines honnêtes — Poisson, Dixon–Coles, cotes de bookmakers, entraînées sur la même information, aux mêmes instants

Jev annonce « calibrated ». Laya va le mesurer : ECE, PIT randomisé, log loss, Brier, RPS — bootstrap groupé + Holm-Bonferroni, sur 2 403 matchs.

Un moteur fermé vous demande de croire ses benchmarks.
Un moteur ouvert vous invite à les vérifier.

Code : https://github.com/steve-dev-55/laya-football-evaluation
Protocole : https://doi.org/10.17605/OSF.IO/TPSQB

#AI #Calibration #OpenSource #SportsAnalytics #ScienceOuverte

---

*Note interne : toutes les affirmations sur Jev proviennent de l'annonce publique TypeSafe AI (lien en tête de fichier). Aucune affiliation entre ce projet et TypeSafe AI ; « version open source de Jev » = positionnement par analogie (moteur de décision probabiliste open source), pas une affirmation technique d'équivalence. Ne pas publier de claim de performance Laya : l'étude n'a pas encore de résultats (phase pré-enregistrement).*
*Astuce portée : publier le lien de l'annonce Jev (https://typesafe.ai/blog/introducing-system-one-models-and-jev) en PREMIER COMMENTAIRE plutôt que dans le post, pour préserver la portée LinkedIn.*
