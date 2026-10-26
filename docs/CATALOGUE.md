# Catalogue : colonnes et décisions

## `catalog/aitmpl_vs_socle.csv`

Une ligne par composant d'aitmpl (1 856 lignes).

| Colonne | Signification |
|---|---|
| `source` | dépôt d'origine du composant |
| `commit` | commit analysé (12 premiers caractères) |
| `path` | chemin du fichier dans le dépôt |
| `type` | `agent`, `skill`, `command`, `hook` ou `mod` |
| `name` | nom du composant |
| `fonction_reelle` | description extraite du fichier (240 caractères maximum) |
| `couche_cible` | couche où le placer : Agent, Skill, Commande, Hook/Mod |
| `equivalent_existant` | meilleur équivalent trouvé dans le Socle, sous la forme `dépôt:chemin` |
| `similarite` | score de 0 à 1 avec cet équivalent |
| `apport_unique_termes` | mots les plus distinctifs du composant, absents de son équivalent |
| `decision` | décision proposée (voir ci-dessous) |
| `justification` | raison en une phrase |

## Valeurs de `decision`

Toutes se terminent par « provisoire (comparaison ZAKI OS manquante) » tant que ZAKI OS n'est pas comparé.

| Valeur | Sens | Prochaine action |
|---|---|---|
| Adopter (apport unique probable) | aucun équivalent proche dans le Socle | lire le composant, puis l'intégrer si la capacité sert un projet |
| Fusionner / Variante | chevauchement partiel avec le Socle | garder ce qui est distinct, fusionner le reste, ou garder comme variante de plateforme |
| Remplacer par le Socle (ou écarter) | fonction déjà couverte | utiliser la version du Socle ; archiver celle d'aitmpl |
| À auditer par comportement | hook ou mod | relever ce qu'il intercepte ou bloque, puis tester les conflits |

Les décisions de la méthode (Conserver, Fusionner, Variante, Remplacer par le Socle, Archiver) sont prises à la relecture, à partir de ces propositions.

## `catalog/socle_index.json`

Index des 1 516 composants du Socle : `source`, `commit`, `path`, `type`, `name`, `description`, `bytes`. Le type `framework` désigne les 4 modules de `claude-swarm`.

## `catalog/agents_index.json`

Index des 422 agents d'aitmpl : `name`, `description`, `tools`, `model`, `bytes`, `category`, `path`.

## `catalog/agents_groups.json`

Les 23 groupes d'agents proches détectés au seuil 0,45. Chaque groupe liste ses membres avec leur taille. Seuls 15 sont de vrais doublons ; le tri est dans `catalog/agents_report.md`.

## Lire le catalogue sur une tablette

Filtrer `aitmpl_vs_socle.csv` sur `decision` commence par « Remplacer » pour voir ce qui est déjà couvert, ou par « Adopter » pour voir les candidats à l'intégration. Trier par `similarite` décroissant fait remonter les quasi-copies (score proche de 1).
