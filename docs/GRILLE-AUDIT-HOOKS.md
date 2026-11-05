# Grille d'audit par comportement des hooks

Un hook n'est jamais décidé par un score (règle ZakiOS). Cette grille liste ce qu'un audit doit prouver avant toute validation humaine. Elle vient de `docs/PRATIQUES.md` (points marqués A) : chaque contrôle est une hypothèse tant que l'essai n'a pas été exécuté.

Preuve attendue : un essai exécuté par sous-processus (comme les essais du dépôt), jamais une lecture seule du script.

| # | Contrôle | Comment l'essayer | Preuve attendue | Écart = |
|---|---|---|---|---|
| 1 | Codes de sortie | Faire échouer le hook de trois façons (succès, code 2, autre code) | 0 laisse passer, 2 bloque avec un message exploitable, autre n'empêche rien | majeur si un blocage prévu ne bloque pas |
| 2 | Boucle d'un hook d'arrêt | Condition volontairement impossible à satisfaire | Le hook s'arrête après un plafond d'itérations et rapporte | bloquant : épuise les tokens |
| 3 | Sortie JSON | Envoyer une sortie invalide et une sortie valide | Erreur lisible, pas de blocage silencieux | majeur |
| 4 | Déclenchement | Exécuter l'événement et la cible (matcher) visés | Le hook s'exécute exactement une fois | majeur si 0 ou 2 fois |
| 5 | Délai maximal | Commande qui dépasse le délai | Interruption propre, état cohérent | majeur |
| 6 | Effets de bord | Comparer l'arbre de fichiers avant et après | Seules les écritures annoncées existent | bloquant si écriture hors périmètre |
| 7 | Lecture de secrets | Placer un faux secret (canari) dans l'environnement et les fichiers | Le canari n'apparaît ni dans la sortie ni dans un journal | bloquant |
| 8 | Réseau et téléchargement | Surveiller les appels sortants | Aucun appel non déclaré, aucun `curl … \| sh` | bloquant |
| 9 | Commandes destructrices | Exécuter avec `rm -rf`, `git reset --hard` dans les entrées | Refus ou confirmation, jamais exécution | bloquant |
| 10 | Idempotence | Exécuter deux fois de suite | Même état final, pas de doublons (cf. ajouts répétés dans un fichier) | mineur |
| 11 | Conflit avec d'autres hooks | Exécuter avec les hooks déjà actifs | Pas de double contrôle ni de contradiction (matrice de conflits, feuille de route 3) | majeur |
| 12 | Retour arrière | Désinstaller | L'état d'avant est restauré sans reste | majeur |

Gravités : celles du Socle (bloquant, majeur, mineur). Constat au format `fichier:ligne · gravité · Problème → Action → Résultat · preuve`.
