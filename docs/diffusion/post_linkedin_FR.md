# Post LinkedIn — Français

**Angle :** pratique et rigoureux — moteurs de décision probabiliste temps réel.
**Placeholders à remplacer avant publication :** [OSF DOI] (assigné à l'étape 3 du processus de publication).
**Longueur cible :** ~200 mots.

---

**On utilise de plus en plus des agents IA comme moteurs de décision en temps réel. Mais qui vérifie si leurs probabilités sont réellement fiables — pendant que le match se joue ?**

Je viens de figer le protocole d'une étude qui fait exactement cela. Le système évalué est un moteur de décision IA typé (Laya) : à chaque snapshot d'un match de football — pré-match, minutes 15 à 85, et juste après chaque but, carton rouge, penalty ou remplacement — il doit produire une distribution de probabilités complète sur le résultat final, 17 catégories de score, les corners et les cartons jaunes.

Quatre choix rendent cette évaluation crédible :

1. **Intégrité point-in-time.** Tests anti-fuite automatiques sur 100 % des snapshots ; tout ce qui n'était pas disponible au cutoff n'atteint jamais le modèle.
2. **Baselines équitables.** Poisson, Dixon–Coles, régression logistique multinomiale, cotes de bookmakers — entraînées sur la même information que l'IA, au même cutoff.
3. **Pré-enregistrement.** Cinq hypothèses, métriques et seuils de blocage figés avant tout contact avec le jeu de test (registered report phase 1 ; pas de résultats pour l'instant, par design).
4. **Reproductibilité totale.** Pipeline à 9 agents, artefacts hashés, open source (MIT / CC-BY 4.0).

Si vous travaillez en sports analytics, en forecasting probabiliste ou en évaluation de LLM, votre critique du protocole est la bienvenue — tant qu'il est encore temps de l'améliorer.

Repo : https://github.com/steve-dev-55/laya-football-evaluation — Pré-enregistrement : [OSF DOI]

#SportsAnalytics #Forecasting #LLM #ScienceOuverte

---

*Note : recompter la longueur après remplacement des placeholders ; viser ~1 300 caractères visibles maximum.*
