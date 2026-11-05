<!-- Modèle ZakiOS (brouillon), contenu original. Checklist de décision avant de construire un agent ou d'en ajouter un. -->
# Échelle de simplicité : ai-je vraiment besoin d'un agent ?

Monter d'un échelon seulement si l'échelon précédent a échoué, preuve à l'appui. Chaque échelon coûte en vitesse, en argent, en testabilité et en surprises.

| Échelon | Quand le choisir | Preuve que l'échelon d'avant ne suffit pas |
|---|---|---|
| 1. Appel unique | Une entrée, une sortie, étapes connues (classer, résumer, extraire) | — |
| 2. Chaîne fixe | Étapes connues d'avance, chacune plus simple qu'un gros appel | L'appel unique est bâclé ; on peut contrôler entre les étapes |
| 3. Routeur | Entrées de natures différentes à orienter vers des traitements spécialisés ; un modèle bon marché trie | Un seul traitement est mauvais ou trop cher pour tous les cas |
| 4. Orchestrateur et exécutants | Sous-tâches indépendantes et découpage non prévisible | La chaîne ne sait pas prévoir les étapes |
| 5. Évaluateur et optimiseur | La qualité prime et « assez bon » est définissable par des critères | La première sortie échoue régulièrement aux critères |
| + Humain dans la boucle | Avant tout acte irréversible (envoi, suppression, dépense, déploiement) | Toujours, pour l'irréversible |

## Avant d'ajouter un agent
- [ ] Un seul agent a été essayé et sa limite est démontrée (mesure, pas impression).
- [ ] Le rôle est une **tâche concrète** (« relire `src/api/` pour l'injection SQL »), pas un personnage (« le consultant prudent »).
- [ ] Les agents ne se contredisent pas : une règle de départage est écrite (qui tranche, qui peut dire non).
- [ ] Un plafond existe : nombre d'appels, de tours, de tokens.
- [ ] Le coût de la coordination est inférieur au gain de qualité (comparer sur 3 passages).
- [ ] Si le système paralyse (tout est refusé, rien n'avance), simplifier d'abord, pas ajouter.
