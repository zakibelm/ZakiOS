# ZakiOS

Catalogue de composants Claude Code (agents, skills, commandes, hooks, mods) **sans redondance**, avec provenance vérifiable.

ZakiOS lit les catalogues publics (aitmpl / davila7/claude-code-templates), les compare à ton Socle .claude (10 dépôts) et, plus tard, à ZAKI OS, puis range chaque composant dans un registre. La méthode s'appelle REA (Reverse Engineering Anything) : on lit ce que fait réellement un composant, on ne se fie pas à son nom.

> **Statut : catalogue exploratoire en lecture seule, avec validation humaine.**
> Ce n'est pas un système d'activation automatique. Un score de similarité est un indice de lecture, jamais une preuve d'équivalence ni de nouveauté. Voir `docs/AUDIT-a29d2df.md`.

## État (moteur 0.2.0, schéma 2)

| Élément | Chiffre |
|---|---|
| Composants indexés | 3 327 (aitmpl 1 809, Socle 1 518) |
| aitmpl par type | 916 skills, 421 agents, 348 commandes, 70 hooks, 45 mods, 9 agents intégrés à des skills |
| Socle par type | 261 skills, 522 agents (+3 intégrés à des skills), 435 commandes, 47 hooks, 246 plugins, 4 modules de framework (détail dans `catalog/build_report.json`) |
| Composants aitmpl évalués | 1 809 : 140 équivalences candidates, 69 chevauchements partiels, 1 485 nouveautés à examiner, 115 audits par comportement (hooks, mods) |
| Fichiers au YAML invalide | 14, signalés dans `build_report.json` (pas masqués) |
| Comparaison avec ZAKI OS | **absente** : tous les résultats portent « comparaison ZAKI OS manquante » |
| Licences vérifiées | 0 : chaque fiche porte `license.verified: false` |

Aucune décision n'est validée par un humain pour l'instant (`decisions/validated.json` est vide).

## Utilisation

```sh
pip install -r requirements.txt            # PyYAML
# cloner les sources aux commits de sources.json sous ./sources/<owner>/<repo>
python3 -m zakios build                    # génère catalog/ (registry.json, crosswalk.csv, build_report.json)
python3 -m zakios verify                   # revalide un catalogue existant
python3 -m unittest discover -s tests -t . # 35 tests
```

Le moteur refuse de construire si une source obligatoire manque, si son commit diffère du manifeste (40 caractères exigés) ou si le dépôt a des modifications locales (`--allow-dirty` pour forcer). La génération se fait dans `catalog.tmp`, est validée, puis remplace `catalog/` d'un bloc : un échec laisse le catalogue précédent intact.

## Structure

```
ZakiOS/
├── sources.json            manifeste : dépôts, rôles, commits complets
├── decisions/validated.json   décisions validées par un humain (jamais écrasées)
├── catalog/                registre généré (ne pas éditer à la main)
├── zakios/                 moteur : parse, classify, policy, scan, similarity, build
├── tests/                  35 tests, sur de petits dépôts git créés à la volée
├── docs/                   méthodologie, catalogue, architecture, feuille de route, audit
└── archive/pre-audit-a29d2df/   ancien catalogue et scripts, gardés pour l'historique seulement
```

## Règles

- Les sources ne sont jamais modifiées.
- Aucun composant tiers n'est copié ici sans licence vérifiée et attribution.
- Chaque fiche garde source, commit complet et empreinte SHA-256 du contenu.
- Un hook, un plugin ou un mod n'est jamais décidé par un score : audit par comportement obligatoire.
- Une règle transversale vit dans le Socle commun, et on vérifie qu'elle arrive bien à chaque agent à l'exécution (test pas encore écrit).

## Licence

Aucune licence n'est encore choisie pour le code de ZakiOS : c'est ta décision. Ce dépôt contient des index, des décisions et le moteur, pas les composants des autres auteurs ; chaque composant garde la licence de sa source (`SOURCES.md`).
