# Sources figées (collecte du 2026-10-26)

Clones superficiels en lecture seule. Le commit identifie exactement ce qui a été analysé.

| Rôle | Dépôt | Commit |
|---|---|---|
| Catalogue analysé | davila7/claude-code-templates (aitmpl.com) | aff83062f3d0e6a882f23e52611d5811539e6047 |
| Socle | wshobson/agents | 0874a27b17a22e2b7c2e2bcd725768e0803cad06 |
| Socle | VoltAgent/awesome-claude-code-subagents | 408d3c9eee2d0c75c12a3abb5de29e53c2ca6b9e |
| Socle | rohitg00/awesome-claude-code-toolkit | ebdf1d596d2cde5c5cceb32177e8d1cf4829e7d9 |
| Socle | anthropics/skills | dbd4588f9e1033efb41dad4bef2f7947c8993d44 |
| Socle | netresearch/claude-code-marketplace | 0ed8b47648cee8dbf30bd4aecd79d6db662c7dcb |
| Socle | disler/claude-code-hooks-mastery | 052ad1cbd5aeb1ec4a1def22012d1293c6225625 |
| Socle | karanb192/claude-code-hooks | 57a28c7687305e4a9b9dd50490e9b3c552c71ca4 |
| Socle | affaan-m/claude-swarm | 9b1c5561157abd2d0d043758b7bfcb0319267d9f |
| Socle | am-will/swarms | 110268148a1fdf149a19e4dab848a1c0fca9835d |
| Socle | eugeniughelbur/obsidian-second-brain | 0e339f7f600af5943042864df63eb142c0c84abf |
| Existant | ZAKI OS (agents et skills) | à identifier |

## Licences

Le catalogue aitmpl agrège des composants de plusieurs auteurs. Ses mods portent des licences MIT avec des auteurs différents. La licence de chaque composant est à vérifier avant de le copier dans cette bibliothèque, et son attribution doit être conservée.

## Notes de structure

- `affaan-m/claude-swarm` est un framework d'orchestration Python (4 modules), pas une collection de composants.
- `netresearch/claude-code-marketplace` est un site de catalogue, sans composants propres.
- `karanb192/claude-code-hooks` fournit un pack de gardes en un seul processus : ne pas l'installer avec les gardes individuels, sinon ils s'exécutent deux fois.
