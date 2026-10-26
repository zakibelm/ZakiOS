# Feuille de route

Ordre fixé par l'audit du commit a29d2df (`docs/AUDIT-a29d2df.md`). Chaque étape dit ce qu'elle apporte.

## Fait (moteur 0.3.0)

- Moteur corrigé : YAML sûr, commits complets, détection des arbres modifiés, comptes sans doublons, statuts prudents, build atomique, 35 tests, puis stabilisation de la version 0.3.0 après le second audit (93449b9) : validations liées à l'empreinte, `verify` complet, échange atomique, verrou, quarantaine des métadonnées invalides, empreinte des composants composés, build expérimental, comparaison entre couches ; 50 tests.
- Conclusions non prouvables retirées (« Adopter », « Remplacer » automatiques).

## À faire

| # | Étape | Bénéfice |
|---|---|---|
| 1 | Localiser les agents et skills ZAKI OS, les ajouter à `sources.json` (rôle existant) | lève le statut « provisoire » ; évite d'adopter ce que tu as déjà |
| 2 | Lire les 15 groupes de vrais doublons d'agents et choisir une version canonique | retire environ 16 agents redondants |
| 3 | Audit par comportement des 115 hooks/mods (sécurité d'abord), matrice de conflits | évite les gardes qui s'exécutent deux fois ou se contredisent |
| 4 | Lire les nouveautés candidates avant de les retenir | une nouveauté lexicale n'est pas une nouveauté réelle |
| 5 | Vérifier les licences des composants retenus | condition pour les copier |
| 6 | Définir le Socle commun et un test de propagation à l'exécution | prouve que chaque agent reçoit les règles |
| 7 | Activation par projet : profil, dépendances, aperçu, fichier de verrouillage, retour arrière | passe du catalogue à l'usage |
| 8 | Intégration continue (tests à chaque push) | empêche les régressions |

## Périmètre V1

Claude Code CLI uniquement. Catalogue en lecture seule par défaut, sélection assistée, activation explicite. Réussite : démontrer le parcours complet sur un projet pilote.

## Décision qui t'attend

Choisir une licence pour le code de ZakiOS.
