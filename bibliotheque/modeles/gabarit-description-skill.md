<!-- Modèle ZakiOS (brouillon), contenu original. Gabarit de SKILL.md : la description décide du déclenchement, c'est la phrase la plus importante. -->
---
name: <nom-court-en-minuscules>
description: <Fais X pour Y. À utiliser quand <situations et mots déclencheurs>. Ne pas utiliser pour <cas voisins exclus>.>
---

# <Titre>

## Quand l'utiliser
- <situation 1, avec les mots que la personne emploie>
- <situation 2>

## Quand ne pas l'utiliser
- <cas voisin qui relève d'un autre skill ou d'une réponse simple>

## Procédure
1. **Planifier** : <ce qu'il faut lire ou demander d'abord>
2. **Exécuter** : <étapes courtes ; détails longs dans des fichiers de référence à côté>
3. **Vérifier** : <critères et preuves>
4. **Agir** : <corrections, livraison>

## Pièges connus
- <erreur fréquente> → <comment l'éviter>

## Fichiers de référence (chargés seulement si nécessaires)
- `reference/<sujet>.md` : <ce qu'il contient>

---
## Contrôle de la description (à faire avant de valider le skill)
- [ ] Elle dit **quoi** et **quand** en une ou deux phrases.
- [ ] Elle contient les mots que la personne emploie réellement.
- [ ] Elle exclut les cas voisins.
- [ ] Test de déclenchement : 3 phrases qui DOIVENT l'activer, 3 qui NE DOIVENT PAS ; noter les résultats.
- [ ] Le corps reste court : le détail va dans les fichiers de référence (le contexte n'est chargé qu'à la demande).
- [ ] Les règles toujours nécessaires sont dans CLAUDE.md ou en hook, pas ici (un skill non chargé n'est pas appliqué).
