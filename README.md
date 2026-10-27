# ZakiOS

Catalogue de composants Claude Code (agents, skills, commandes, hooks, mods) **sans redondance**, avec provenance vérifiable.

ZakiOS lit les catalogues publics (aitmpl / davila7/claude-code-templates), les compare à ton Socle .claude (10 dépôts) et, plus tard, à ZAKI OS, puis range chaque composant dans un registre. La méthode s'appelle REA (Reverse Engineering Anything) : on lit ce que fait réellement un composant, on ne se fie pas à son nom.

> **Statut : catalogue exploratoire en lecture seule, avec validation humaine.**
> Ce n'est pas un système d'activation automatique. Un score de similarité est un indice de lecture, jamais une preuve d'équivalence ni de nouveauté. Voir `docs/AUDIT-a29d2df.md`.

## État (moteur 0.6.0, schéma 5)

| Élément | Chiffre |
|---|---|
| Composants indexés | 3 327 (aitmpl 1 809, Socle 1 518) |
| aitmpl par type | 916 skills, 421 agents, 348 commandes, 70 hooks, 45 mods, 9 agents intégrés à des skills |
| Socle par type | 261 skills, 522 agents (+3 intégrés à des skills), 435 commandes, 47 hooks, 246 plugins, 4 modules de framework (détail dans `catalog/build_report.json`) |
| Composants aitmpl évalués | 1 809 : 140 équivalences candidates, 69 chevauchements partiels, 53 chevauchements inter-couches, 1 432 nouveautés à examiner, 115 audits par comportement (hooks, mods) |
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
python3 -m unittest discover -s tests -t . # 266 tests
```

Le moteur refuse de construire si une source obligatoire manque, si son commit diffère du manifeste (40 caractères exigés) ou si le dépôt a des modifications locales. `--allow-dirty` donne un build **expérimental** (`build_mode: experimental_dirty`), à ne pas présenter comme une reconstruction exacte. Un verrou empêche deux générations simultanées. La génération se fait dans un dossier temporaire unique, est validée, puis remplace `catalog/` par un échange atomique : un lecteur voit toujours soit l'ancien, soit le nouveau catalogue. `verify` lit les trois fichiers d'une même génération, puis recalcule le CSV, les comptes et les références à partir du registre. La génération précédente est gardée dans `catalog.prev`.

**Plateforme prise en charge : Linux** (échange atomique et verrou `fcntl`). Ailleurs, le build refuse de démarrer faute de verrou.

## Structure

```
ZakiOS/
├── sources.json            manifeste : dépôts, rôles, commits complets
├── decisions/              validated.json (décisions), licenses.json (licences vérifiées), annotations.json (dépendances, conflits, compatibilité)
├── catalog/                registre généré (ne pas éditer à la main)
├── zakios/                 moteur : parse, classify, policy, scan, similarity, build
├── tests/                  266 tests, sur de petits dépôts git créés à la volée
├── docs/                   méthodologie, catalogue, architecture, activation, revues de lots, feuille de route, audits
└── archive/pre-audit-a29d2df/   ancien catalogue et scripts, gardés pour l'historique seulement
```

## Activation dans un projet (pilote)

`plan` (aperçu sans écriture), `apply` (installation tout ou rien, réexécutable) et `rollback` installent des composants validés dans `.claude/` d'un projet Linux. Rien n'est installable tant qu'un humain n'a pas validé la décision et la licence : aujourd'hui, aucun composant réel. Détails et garanties : `docs/ACTIVATION.md`.

## Règles

- Les sources ne sont jamais modifiées.
- Aucun composant tiers n'est copié ici sans licence vérifiée et attribution.
- Chaque fiche garde source, commit complet et empreinte SHA-256 du contenu.
- Un hook, un plugin ou un mod n'est jamais décidé par un score : audit par comportement obligatoire.
- Un composant aux métadonnées invalides n'est jamais utilisé comme référence, voisin ou homonyme.
- Une décision humaine est liée à l'empreinte du paquet complet du composant (scripts, ressources et imports locaux compris) : si son contenu change, la validation est marquée périmée et doit être refaite.
- Une règle transversale vit dans le Socle commun, et on vérifie qu'elle arrive bien à chaque agent à l'exécution (test pas encore écrit).

## Licence

Aucune licence n'est encore choisie pour le code de ZakiOS : c'est ta décision. Ce dépôt contient des index, des décisions et le moteur, pas les composants des autres auteurs ; chaque composant garde la licence de sa source (`SOURCES.md`).
