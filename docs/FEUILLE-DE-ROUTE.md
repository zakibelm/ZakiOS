# Feuille de route

Ordre fixé par l'audit du commit a29d2df (`docs/AUDIT-a29d2df.md`). Chaque étape dit ce qu'elle apporte.

## Fait (moteur 0.6.0)

- Moteur corrigé : YAML sûr, commits complets, détection des arbres modifiés, comptes sans doublons, statuts prudents, build atomique, 35 tests, puis stabilisation de la version 0.3.0 après le second audit (93449b9) : validations liées à l'empreinte, `verify` complet, échange atomique, verrou, quarantaine des métadonnées invalides, empreinte des composants composés, build expérimental, comparaison entre couches ; 50 tests, puis troisième tour (8e6bc0b) : quarantaine étendue aux références, empreintes de paquets complets, lecture cohérente d'une génération, Linux déclaré ; 60 tests ; quatrième tour (3b21861) : parcours des dépendances sans plafond, empreintes incomplètes déclarées (64 tests) ; pilote d'activation sur composants fictifs : aperçu, installation tout ou rien, réexécution sans duplication, retour arrière (94 tests) ; cinquième tour (d9ca9c0) : accès confiné au projet sans suivre les liens symboliques, restaurations sans écrasement, reprise après interruption avec contrôle des modifications utilisateur (102 tests) ; sixième tour (0f8cdef) : reprise après interruption avant la validation du plan, preuve par sous-processus tué (106 tests) ; 0.6.0 : composants propres (rôle `propre`), Socle installable, premier essai de comportement relecteur/planificateur par le moteur (115 tests) ; enregistrement contrôlé des plans `save-plan` et essai de bout en bout demande → plan → aperçu → enregistrement (135 tests) ; identité de livraison (`delivery_sha256`) et format de livrable explicite (140 tests).
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
| 7 | Activation par projet : pilote **fait** (aperçu, tout ou rien, retour arrière) ; reste le premier lot réel sur projet jetable | passe du catalogue à l'usage |
| 8 | Intégration continue : **faite** (tests + `verify`) | empêche les régressions |
| 9 | Profil de travail, règles de décision, mémoire par projet, délégation, mesure d'utilité (`docs/PROFIL.md`) | fait de ZakiOS ton Socle personnel, pas un simple échantillon |
| 11 | Architecture cible : demande en langage naturel → orchestration PDCA → résultat avec preuves, routage OpenRouter/OmniRoute (`docs/CIBLE.md`) ; **objectif à vérifier, non acquis** | ZakiOS devient un système d'usage, pas seulement un catalogue |
| 10 | Lot 1 en variantes ZakiOS : relecteur, planificateur, lanceur de tests | premier composant à ta mesure |

## Périmètre V1

Claude Code CLI uniquement. Catalogue en lecture seule par défaut, sélection assistée, activation explicite. Réussite : démontrer le parcours complet sur un projet pilote.

## Jalon de coordination (mesuré, un critère non satisfait)

Rôle `plan-reviewer` (lecture seule) et coordinateur déterministe `zakios/mission.py` (boucle PDCA, plafond, trace, livraison contrôlée), testés sans modèle puis avec modèle sur 3 passages. Détection et correction des écarts injectés : 3/3. Faux positif du témoin : 1 passage sur 3 → critère « témoin accepté au premier tour » **non satisfait**. Détail et pistes : `docs/revues/essai-coordination.md`. `plan-reviewer` doit passer la même revue humaine que le lot 1 avant toute installation réelle.

## Décision qui t'attend

Choisir une licence pour le code de ZakiOS.
