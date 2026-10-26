# ZakiOS

Bibliothèque de composants Claude Code (agents, skills, commandes, hooks, mods) **sans redondance**.

ZakiOS part des catalogues publics, les compare à ce que tu possèdes déjà (le Socle .claude et les composants ZAKI OS) et décide, composant par composant, ce qui mérite d'entrer. La méthode s'appelle REA (Reverse Engineering Anything) : on lit ce que fait réellement chaque composant, on ne se fie pas à son nom.

**Idée directrice : une bibliothèque complète en réserve, et seulement les composants nécessaires activés par projet.**

## Pourquoi

Les grands catalogues se recoupent fortement. Rien que dans les agents d'aitmpl, plus d'un sur cinq a un équivalent proche dans le Socle, et 40 composants sont des copies quasi identiques. Installer « tout » alourdit le contexte, répète les règles et crée des conflits entre hooks. ZakiOS garde un seul exemplaire de chaque capacité, avec sa source, son commit et sa décision.

## État au 2026-10-26

| Élément | Chiffre |
|---|---|
| Composants aitmpl analysés | 1 856 (916 skills, 431 agents, 349 commandes, 115 hooks, 45 mods) |
| Composants du Socle des 10 dépôts | 1 516 (525 agents, 437 commandes, 289 hooks, 261 skills, 4 modules de framework) |
| Agents aitmpl : groupes de vrais doublons | 15 groupes (31 agents), soit environ 16 agents retirables |
| Comparaison avec ZAKI OS | **pas encore faite** : toutes les décisions sont provisoires |

Limites connues : la comparaison est lexicale (voir `docs/METHODOLOGIE.md`), les hooks et mods demandent un audit par comportement, et le test de propagation des règles du Socle aux agents reste à faire.

## Structure du dépôt

```
ZakiOS/
├── README.md              ce fichier
├── SOURCES.md             dépôts sources, commits figés, notes de licence
├── catalog/
│   ├── aitmpl_vs_socle.csv    table de décision (1 856 lignes)
│   ├── socle_index.json       index des 1 516 composants du Socle
│   ├── agents_index.json      index des agents aitmpl
│   ├── agents_groups.json     groupes de doublons détectés
│   └── agents_report.md       rapport de redondance des agents
├── docs/
│   ├── METHODOLOGIE.md        comment les décisions sont produites
│   ├── CATALOGUE.md           dictionnaire des colonnes et des décisions
│   ├── ARCHITECTURE.md        couches, réserve et activation par projet
│   └── FEUILLE-DE-ROUTE.md    prochaines étapes, avec leur bénéfice
└── tools/
    ├── crosswalk.py           indexe le Socle et croise avec aitmpl
    └── index_agents.py        indexe les agents et détecte les doublons
```

## Démarrage rapide

1. Lire `docs/CATALOGUE.md` pour comprendre les colonnes.
2. Ouvrir `catalog/aitmpl_vs_socle.csv` et filtrer sur la colonne `decision`.
3. Pour régénérer les catalogues, cloner les sources aux commits de `SOURCES.md` sous `/home/claude/<owner>/<repo>`, puis :

```sh
python3 -I tools/crosswalk.py catalog/
python3 -I tools/index_agents.py <chemin>/cli-tool/components/agents catalog/ 0.45
```

Les scripts n'utilisent que la bibliothèque standard de Python 3.

## Règles du projet

- Les sources ne sont jamais modifiées.
- Aucun composant tiers n'est copié ici sans sa licence et son attribution.
- Chaque ligne du catalogue garde sa source et son commit.
- Une décision est « provisoire » tant que la comparaison avec ZAKI OS n'est pas faite.
- Une règle transversale vit à un seul endroit, le Socle commun, et on vérifie que chaque agent la reçoit à l'exécution.

## Licence et attribution

Ce dépôt contient des index, des décisions et des scripts, pas les composants des autres auteurs. Chaque composant garde la licence de sa source : voir `SOURCES.md`.
