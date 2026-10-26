# ZakiOS

Bibliothèque de composants Claude Code (agents, skills, commandes, hooks, mods) **sans redondance**, construite par reverse engineering (REA) à partir de catalogues publics et comparée au Socle .claude et aux composants ZAKI OS.

Principe : une bibliothèque complète en réserve, et seulement les composants nécessaires activés par projet.

## Structure

| Dossier | Contenu |
|---|---|
| `catalog/` | Index des composants et table de décision (aitmpl vs Socle) |
| `tools/` | Scripts d'indexation et de croisement (Python, bibliothèque standard) |
| `SOURCES.md` | Dépôts sources, commits figés, notes de licence |

## Décisions possibles par composant

- **Conserver** : capacité utile et distincte.
- **Fusionner** : même responsabilité, apports compatibles.
- **Variante** : spécialisation ou plateforme différente.
- **Remplacer par le Socle** : instruction transversale déjà centralisée.
- **Archiver** : obsolète, incompatible ou sans valeur supplémentaire.
- **À auditer par comportement** : hooks et mods, où la similarité de texte ne suffit pas.

## État (2026-10-26)

- 1 856 composants aitmpl comparés à 1 516 composants du Socle des 10 dépôts (`catalog/aitmpl_vs_socle.csv`).
- Toutes les décisions sont **provisoires** : la comparaison avec les agents et skills ZAKI OS n'est pas faite.
- La comparaison est lexicale. « Adopter » est une indication à confirmer par lecture, surtout pour les commandes.
- Hooks et mods : audit par comportement et matrice de conflits à faire.
- À tester : que chaque agent reçoit bien les règles transversales du Socle à l'exécution.

## Régénérer

Les scripts attendent les dépôts clonés sous `/home/claude/<owner>/<repo>` (voir `SOURCES.md`) :

```sh
python3 -I tools/crosswalk.py catalog/
python3 -I tools/index_agents.py <chemin>/cli-tool/components/agents catalog/ 0.45
```

## Règles

- Les sources ne sont jamais modifiées.
- Aucun composant tiers n'est copié ici sans sa licence et son attribution.
- Chaque ligne du catalogue garde sa source et son commit.
