# Catalogue : fiches et statuts

## Fichiers générés (`catalog/`)

- `registry.json` : une fiche par composant (source de vérité).
- `crosswalk.csv` : vue à plat des composants **aitmpl** évalués, pour filtrer sur une tablette.
- `build_report.json` : comptes par source et par type, fichiers au YAML invalide, décisions orphelines, empreinte du manifeste.

## Fiche (schéma 2)

| Champ | Contenu |
|---|---|
| `component_id` | `dépôt:chemin`, unique |
| `type` | skill, agent, embedded_agent, command, hook, plugin, mod, framework_module |
| `provenance` | dépôt, rôle, chemin, **commit complet**, SHA-256 du contenu |
| `function.summary` | description lue dans le fichier (240 caractères maximum) |
| `compatibility`, `relations` | outils requis, dépendances, conflits : vides pour l'instant |
| `license` | `verified: false` tant que personne n'a lu la licence |
| `evaluation` | meilleur équivalent, score, voisins, homonyme, statut proposé (aitmpl seulement) |
| `decision` | `validated` : vide jusqu'à validation humaine |
| `metadata_issue` | YAML invalide ou autre problème, jamais masqué |

## Statuts proposés

| Statut | Seuil | Sens | Action humaine |
|---|---|---|---|
| Équivalence candidate | score ≥ 0,60 | proche d'un composant existant | lire les deux, puis conserver, remplacer ou fusionner |
| Chevauchement partiel | ≥ 0,40 | recoupement | garder ce qui est distinct |
| Nouveauté à examiner | < 0,40 | pas d'équivalent lexical | lire : l'absence de score ne prouve pas la nouveauté |
| Audit par comportement | hook, plugin, mod | jamais décidé par un score | relever ce qu'il intercepte, bloque, modifie |
| Métadonnées insuffisantes | pas de texte | impossible à comparer | lire le fichier |

Les statuts sont des propositions. Les décisions (Conserver, Fusionner, Variante, Remplacer par le Socle, Archiver) sont prises par un humain et inscrites dans `decisions/validated.json`, fusionnées au prochain build sans jamais être écrasées. Une décision dont le composant a disparu est listée comme orpheline.

## Archive

`archive/pre-audit-a29d2df/` contient l'ancien catalogue (1 856 lignes, libellés « Adopter / Remplacer »). Il est conservé pour l'historique : ses chiffres (289 hooks du Socle, plugin.json comptés comme hooks, mods comptés plusieurs fois) étaient faux.
