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
| `provenance` | dépôt, rôle, chemin, **commit complet**, SHA-256 du fichier, `fingerprint_sha256` et `fingerprint_files` (paquet complet : dossier entier d'un mod ou d'un skill ; pour un hook, sa configuration, ses scripts du même nom ou cités ; pour un plugin, son manifeste, hooks, scripts et .mcp.json ; et, pour tous, les imports locaux détectés dans les scripts, transitivement) ; `fingerprint_complete` et `fingerprint_unexplored` disent si le parcours est allé au bout |
| `function.summary` | description lue dans le fichier (240 caractères maximum) |
| `compatibility`, `relations` | outils requis, dépendances, conflits : vides pour l'instant |
| `license` | `verified: false` tant que personne n'a lu la licence |
| `evaluation` | meilleur équivalent, score, voisins, homonymes, correspondances inter-couches, statut proposé (aitmpl seulement) |
| `decision` | `validated` : vide jusqu'à validation humaine ; `validated_fingerprint_sha256` ; `stale_validation` si le contenu a changé |
| `metadata_issue` | YAML invalide ou autre problème, jamais masqué |

## Statuts proposés

| Statut | Seuil | Sens | Action humaine |
|---|---|---|---|
| Équivalence candidate | score ≥ 0,60 | proche d'un composant existant | lire les deux, puis conserver, remplacer ou fusionner |
| Chevauchement partiel | ≥ 0,40 | recoupement | garder ce qui est distinct |
| Nouveauté à examiner | < 0,40 | pas d'équivalent lexical | lire : l'absence de score ne prouve pas la nouveauté |
| Chevauchement inter-couches | score < 0,40 dans sa famille mais ≥ 0,40 avec une autre famille | la capacité existe peut-être dans un skill, un agent ou une commande | lire le composant proche avant de conclure à la nouveauté |
| Métadonnées invalides | fichier mal lu | mis en quarantaine, non comparé | corriger ou lire le fichier |
| Audit par comportement | hook, plugin, mod | jamais décidé par un score | relever ce qu'il intercepte, bloque, modifie |
| Métadonnées insuffisantes | pas de texte | impossible à comparer | lire le fichier |

## Valider une décision

Dans `decisions/validated.json`, une entrée par composant :

```json
{"dépôt:chemin": {"validated": "conserver", "validated_by": "Zaki", "validated_on": "2026-10-26",
  "justification": "mission distincte", "fingerprint_sha256": "<empreinte lue dans registry.json>"}}
```

Licences (`decisions/licenses.json`) : `{"dépôt ou dépôt:chemin": {"spdx": "MIT", "verified_by": "Zaki", "commit": "<commit lu>", "attribution": "…"}}`. Une vérification liée à un autre commit est périmée (`stale_licenses`). Annotations (`decisions/annotations.json`) : `depends_on`, `conflicts_with`, `variant_of`, `replaced_by`, `platform`, `min_version` par composant.

Valeurs autorisées : `conserver`, `fusionner`, `variante`, `remplacer_par_socle`, `archiver`. Sans empreinte, ou si le contenu a changé depuis, la validation n'est pas appliquée et apparaît dans `stale_decisions` du rapport.

Les statuts sont des propositions. Les décisions (Conserver, Fusionner, Variante, Remplacer par le Socle, Archiver) sont prises par un humain et inscrites dans `decisions/validated.json`, fusionnées au prochain build sans jamais être écrasées. Une décision dont le composant a disparu est listée comme orpheline.

## Archive

`archive/pre-audit-a29d2df/` contient l'ancien catalogue (1 856 lignes, libellés « Adopter / Remplacer »). Il est conservé pour l'historique : ses chiffres (289 hooks du Socle, plugin.json comptés comme hooks, mods comptés plusieurs fois) étaient faux.
