# Sources figées

Le fichier de référence est `sources.json` (commits complets de 40 caractères). Le moteur refuse de construire si un dépôt n'est pas exactement à ce commit ou s'il a des modifications locales. Clones superficiels, lecture seule, sous `sources/<owner>/<repo>`.

| Rôle | Dépôt | Commit | Composants |
|---|---|---|---|
| Catalogue | davila7/claude-code-templates (aitmpl.com), sous-dossier `cli-tool/components` | aff83062f3d0e6a882f23e52611d5811539e6047 | 1 809 |
| Socle | wshobson/agents | 0874a27b17a22e2b7c2e2bcd725768e0803cad06 | 588 |
| Socle | rohitg00/awesome-claude-code-toolkit | ebdf1d596d2cde5c5cceb32177e8d1cf4829e7d9 | 579 |
| Socle | VoltAgent/awesome-claude-code-subagents | 408d3c9eee2d0c75c12a3abb5de29e53c2ca6b9e | 173 |
| Socle | disler/claude-code-hooks-mastery | 052ad1cbd5aeb1ec4a1def22012d1293c6225625 | 57 |
| Socle | eugeniughelbur/obsidian-second-brain | 0e339f7f600af5943042864df63eb142c0c84abf | 57 |
| Socle | karanb192/claude-code-hooks | 57a28c7687305e4a9b9dd50490e9b3c552c71ca4 | 30 |
| Socle | anthropics/skills | dbd4588f9e1033efb41dad4bef2f7947c8993d44 | 23 |
| Socle | am-will/swarms | 110268148a1fdf149a19e4dab848a1c0fca9835d | 7 |
| Socle | affaan-m/claude-swarm | 9b1c5561157abd2d0d043758b7bfcb0319267d9f | 4 (modules de framework) |
| Socle | netresearch/claude-code-marketplace | 0ed8b47648cee8dbf30bd4aecd79d6db662c7dcb | 0 (site de catalogue) |
| Existant | ZAKI OS (zakibelm/ZAKI-OS-a-designer, emplacement à confirmer) | non figé | **absent** |

Le dépôt ZAKI OS est déclaré dans `sources.json` comme source facultative : tant qu'il manque, tout le catalogue est marqué « provisoire — comparaison ZAKI OS manquante ».

## Licences

Aucune licence n'est vérifiée à ce stade : chaque fiche a `license.verified: false`. Le catalogue aitmpl agrège des composants de plusieurs auteurs, avec des licences potentiellement différentes. Rien n'est copié dans ZakiOS tant que la licence du composant n'est pas lue et son attribution notée.

## Notes de structure

- `affaan-m/claude-swarm` est un framework Python d'orchestration : 4 modules (orchestrateur, décomposeur, contrôle qualité, session), pas une collection.
- `karanb192/claude-code-hooks` fournit un pack de 7 gardes dans un seul processus : ne pas l'installer avec les gardes individuels.
- Un mod aitmpl est **un seul composant** (son README). Son plugin.json et ses hooks internes ne sont pas comptés à part.
