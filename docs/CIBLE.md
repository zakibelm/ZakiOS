# Architecture cible (objectif à construire et à vérifier — rien ici n'est un acquis)

Statut de chaque bloc : **cible** tant qu'il n'a pas réussi une mission complète de bout en bout. Aucune capacité ci-dessous n'est démontrée aujourd'hui, sauf mention « existant ».

## Chaîne visée

Demande en langage naturel → orchestration **PDCA** → résultat **avec preuves**.

| Étape | Ce qui doit se passer | État |
|---|---|---|
| Planifier | Besoin, situation initiale, critères d'acceptation | cible |
| Choisir la source | 1. pratiques déjà validées (décisions, Socle) ; 2. recherche dans le catalogue GitHub ; 3. recherche Web. Justifier : **réutiliser, adapter, combiner ou développer** | cible (catalogue + décisions : existant) |
| Contrôler | Licences, dépendances, compatibilité avant toute copie | existant (moteur 0.5.2) pour le catalogue ; cible pour le Web |
| Exécuter | Installation contrôlée des composants | **existant** (pilote `plan`/`apply`/`rollback`) |
| Exécuter | Exécution des agents sous restrictions techniques (outils retirés, bac à sable, limites) | **cible** ; variantes en brouillon, restrictions non démontrées |
| Vérifier / Agir | Preuves, écarts, corrections, standardisation | cible |

## Rétro-ingénierie

Sert à comprendre une base de code ou un **comportement observable**. Elle ne suppose jamais l'accès au code d'une application : sans code, on observe (interfaces, sorties, documentation publique) et on déclare ce qui reste inconnu.

## Séparation par utilisateur

Préférences, mémoires, projets, permissions et budgets sont séparés **par utilisateur**. Le profil de Zaki (`docs/PROFIL.md`) est un **profil de départ adaptable**, pas une règle imposée à d'autres. Cible : aucun partage implicite entre utilisateurs ; budgets et permissions propres à chacun.

## Routage de modèles : OpenRouter et OmniRoute

Intégrés à la cible, derrière une couche d'abstraction (fournisseurs interchangeables). Sélection du modèle selon la mission, le coût (en $ CAD) et des modèles de secours.
**Avant de fixer la configuration** : confirmer par test réel les capacités exactes (modèles disponibles, limites, tarifs, langues, appels d'outils, comportement de repli). Aucun modèle ni tarif n'est figé dans ce dépôt tant que ce test n'est pas fait.

## Registre des outils logiciels réutilisables (cible)

Registre distinct des agents et des skills : programmes, bibliothèques et services réutilisables, chacun avec source, licence, dépendances, compatibilité, version figée et usage autorisé. Consulté à l'étape « Choisir la source » avant de développer.

## Priorité de coût pour les modèles (cible)

Modèles gratuits ou économiques d'abord, tant qu'ils satisfont les critères de qualité de la mission. Chaque mission porte un **plafond budgétaire** (en $ CAD), un **nombre maximal de tentatives** et une **condition d'arrêt** ; au-delà, arrêt et rapport, jamais d'escalade silencieuse.

## Règles de portée

- Le PDCA remplace EVV/EVV+ **dans ZakiOS seulement** ; aucun système extérieur n'est modifié automatiquement.
- Le Socle porte les règles communes **une seule fois** ; son chargement est prouvé par test de comportement, pas déduit d'un marqueur.
- Une capacité passe de « cible » à « démontrée » seulement après une mission complète réussie, avec ses preuves.

## Premier jalon de vérification

Lot 1 sur projet jetable : installation des trois variantes, test de comportement (marqueur + règles suivies), réexécution sans duplication, retour arrière. C'est la première preuve partielle ; elle ne couvre ni le Web, ni le routage, ni la séparation par utilisateur.
