# Revue du lot 1 (projet jetable) — dossiers à valider

Statut : **revue préparée, rien n'est validé ni installé.** `decisions/validated.json`, `licenses.json` et `annotations.json` sont inchangés. Les extraits JSON ci-dessous sont à copier **seulement si tu valides**.

Catalogue lu : davila7/claude-code-templates au commit `aff83062f3d0e6a882f23e52611d5811539e6047`, génération 0.5.2. Hooks exclus du lot.

## Aperçu d'essai (avec de fausses validations, dans un dossier temporaire)

```
create  .claude/agents/code-reviewer.md
create  .claude/commands/test-coverage.md
create  .claude/skills/writing-plans/SKILL.md
```

Trois fichiers, aucun script, aucune dépendance hors paquet, aucune modification de `settings.json`. Les vraies décisions n'ont pas été touchées.

## 1. Agent — revue de code : `agents/development-tools/code-reviewer.md`

| | |
|---|---|
| Identifiant | `davila7/claude-code-templates:cli-tool/components/agents/development-tools/code-reviewer.md` |
| Empreinte | `b98a22896c90d0e2b1a98774fd13e240eebea0c8fd141b31f07e6ec342f9db47` (1 fichier, 9,7 Ko) |
| Fonction réelle | Relecture de diff : périmètre selon la taille du changement, pré-contrôles (CVE de dépendances, secrets codés en dur), checklist sécurité / erreurs / tests / perf, contrôles par langage (TypeScript, Python, Rust, Go, SQL), format de sortie par gravité avec recommandation de fusion |
| Équivalent existant | **Oui, dans ton Socle** : `code-reviewer` de VoltAgent et celui de rohitg00 (même nom, même mission) |
| Apport unique | Stratégie « diff d'abord », pré-contrôles outillés, contrôles par langage, format de sortie gravité + recommandation. La version VoltAgent n'en contient aucun (vérifié par recherche des termes). |

**Problème 1 — doublon de nom.** Le Socle fournit déjà un `code-reviewer.md` : installer les deux dans un même projet les ferait se marcher dessus (même nom de fichier). **Action :** n'en activer qu'un par projet ; dans le projet jetable, seule la version aitmpl. **Bénéfice :** on compare les deux sur un vrai diff sans conflit.

**Problème 2 — droits trop larges pour une relecture.** Outils déclarés : Read, Write, Edit, Bash, Glob, Grep. Un relecteur n'a pas besoin d'écrire, et il lance des commandes (`npm audit`, `grep`, `git diff`). Les versions du Socle ont les mêmes droits. **Action :** projet jetable uniquement ; si l'agent est retenu, on pourra le dériver avec Read, Glob, Grep et Bash limité (le moteur copie tel quel, il faudra alors créer une variante ZAKI OS). **Bénéfice :** aucune écriture inattendue pendant une revue.

**Problème 3 — attribution.** Dépôt aitmpl : MIT, « Copyright (c) 2025 Daniel (San) Ávila » (LICENSE lu). Le début du texte est identique à celui de VoltAgent (MIT, « Copyright (c) 2025 VoltAgent », lu aussi) : la source d'origine est probablement VoltAgent. **Action :** noter les deux dans l'attribution. **Bénéfice :** licence respectée si tu l'utilises ou la diffuses.

**Décision proposée :** `variante` (garder la version aitmpl comme variante enrichie du `code-reviewer` du Socle, jamais les deux en même temps). Alternative : `remplacer_par_socle` si tu préfères ta version actuelle.

```json
// decisions/validated.json
{"davila7/claude-code-templates:cli-tool/components/agents/development-tools/code-reviewer.md":
 {"validated": "variante", "validated_by": "<ton nom>", "validated_on": "<date>",
  "justification": "variante enrichie du code-reviewer du Socle ; un seul actif par projet",
  "fingerprint_sha256": "b98a22896c90d0e2b1a98774fd13e240eebea0c8fd141b31f07e6ec342f9db47"}}
```

## 2. Skill — planification d'implémentation : `skills/development/writing-plans/SKILL.md`

| | |
|---|---|
| Identifiant | `davila7/claude-code-templates:cli-tool/components/skills/development/writing-plans/SKILL.md` |
| Empreinte | `15005e7ac7e531488f1d5b2f9809af466a4037634c21c04706f1320453cb7cf0` (1 fichier, 3,3 Ko) |
| Fonction réelle | À partir d'une spec, écrit un plan en tâches de 2 à 5 minutes (test qui échoue, implémentation minimale, test qui passe, commit), enregistré dans `docs/plans/AAAA-MM-JJ-<fonction>.md`, puis propose deux modes d'exécution |
| Équivalent existant | Aucun proche dans le Socle (meilleur score 0,16). `swarm-planner` (am-will/swarms) fait de la planification dépendante mais pour des essaims. |
| Apport unique | Plans prêts à exécuter, TDD, commits fréquents, chemins et commandes exacts |

**Problème 1 — copie double.** Le même fichier existe sous `skills/productivity/writing-plans/` (identique, score 1,0). **Action :** retenir `development/` comme version canonique et proposer `archiver` pour l'autre. **Bénéfice :** une seule copie dans la bibliothèque.

**Problème 2 — renvois vers des skills externes.** Le texte demande `superpowers:executing-plans` et `superpowers:subagent-driven-development`, et mentionne un skill de brainstorming. Ils existent dans le catalogue (`executing-plans`, `subagent-driven-development`, `brainstorming`) mais sous un autre nom que `superpowers:`. **Action :** ne pas déclarer de dépendance obligatoire (le plan reste utile seul) ; ajouter `executing-plans` au lot 2 si tu veux le parcours complet. **Bénéfice :** lot minimal, sans installation en cascade.

**Problème 3 — licence d'origine non lue.** La README d'aitmpl attribue ce groupe de skills à obra/superpowers (MIT). Je n'ai pas pu lire le LICENSE de ce dépôt (domaine non autorisé dans cette session). **Action :** ouvre le LICENSE de obra/superpowers et recopie la ligne de copyright ; sans cela, ne valide pas la licence. **Bénéfice :** la licence vérifiée repose sur le texte réel.

**Effet de bord à connaître :** le skill écrit des fichiers sous `docs/plans/` du projet. Sans danger sur un projet jetable.

**Décision proposée :** `conserver`.

```json
// decisions/validated.json
{"davila7/claude-code-templates:cli-tool/components/skills/development/writing-plans/SKILL.md":
 {"validated": "conserver", "validated_by": "<ton nom>", "validated_on": "<date>",
  "justification": "planification TDD sans équivalent dans le Socle ; copie productivity/ à archiver",
  "fingerprint_sha256": "15005e7ac7e531488f1d5b2f9809af466a4037634c21c04706f1320453cb7cf0"},
 "davila7/claude-code-templates:cli-tool/components/skills/productivity/writing-plans/SKILL.md":
 {"validated": "archiver", "validated_by": "<ton nom>", "validated_on": "<date>",
  "justification": "copie identique de development/writing-plans",
  "fingerprint_sha256": "15005e7ac7e531488f1d5b2f9809af466a4037634c21c04706f1320453cb7cf0"}}
```

## 3. Commande — tests du projet : `commands/testing/test-coverage.md`

| | |
|---|---|
| Identifiant | `davila7/claude-code-templates:cli-tool/components/commands/testing/test-coverage.md` |
| Empreinte | `189de61fe643d9efca32aba787f4b5151a80b62386a23f098be3f1942d0e75f0` (1 fichier, 2,4 Ko) |
| Fonction réelle | **Analyse de couverture** : détecte l'outil (Jest, nyc, Coverage.py, JaCoCo), mesure, repère les trous, propose des tests. Elle **ne se contente pas d'exécuter les tests.** |
| Équivalent existant | Aucun proche (score 0,24) |

**Problème 1 — pas de commande « lancer les tests » dans le catalogue.** Les commandes du dossier `testing/` génèrent ou analysent des tests (`generate-tests`, `write-tests`, `test-coverage`, `flaky-test-triage`…), aucune ne se limite à les exécuter. **Action :** au choix, (a) prendre `test-coverage` comme approximation, (b) écrire une commande `run-tests` à toi (ZAKI OS), courte et portable, que je peux ajouter comme source « existant », ou (c) laisser la commande hors du lot 1. **Bénéfice :** le lot reflète la fonction voulue, sans composant qui promet autre chose.

**Problème 2 — exécution de commandes à la lecture.** Le fichier contient des lignes `!` (`find`, `npm ls`, `wc`) exécutées au lancement, et déclare Read, Write, Edit, Bash. Ce sont des lectures sans effet de bord, mais la commande peut ensuite modifier des fichiers. **Action :** projet jetable ; relire le texte avant la première utilisation. **Bénéfice :** rien d'inattendu.

**Problème 3 — orientation JavaScript.** Les détections couvrent surtout Jest et nyc. **Action :** tester sur un projet JS jetable. **Bénéfice :** on juge sur un cas réaliste.

**Décision proposée :** `conserver` pour l'essai seulement si tu choisis (a) ; sinon aucune validation.

```json
// decisions/validated.json
{"davila7/claude-code-templates:cli-tool/components/commands/testing/test-coverage.md":
 {"validated": "conserver", "validated_by": "<ton nom>", "validated_on": "<date>",
  "justification": "analyse de couverture, essai sur projet jetable",
  "fingerprint_sha256": "189de61fe643d9efca32aba787f4b5151a80b62386a23f098be3f1942d0e75f0"}}
```

## Licence commune aux trois (à compléter par toi)

Le dépôt est sous MIT (Daniel (San) Ávila). Les trois composants viennent d'auteurs d'origine possibles différents (VoltAgent, obra/superpowers, inconnu pour la commande). Une vérification par dépôt ne suffit donc pas : fais-la **par composant**.

```json
// decisions/licenses.json  (commit = celui du catalogue lu)
{"davila7/claude-code-templates:cli-tool/components/agents/development-tools/code-reviewer.md":
 {"spdx": "MIT", "verified_by": "<ton nom>", "verified_on": "<date>",
  "commit": "aff83062f3d0e6a882f23e52611d5811539e6047",
  "attribution": "Daniel (San) Ávila (aitmpl) ; texte d'origine probable : VoltAgent (MIT)"}}
```

À faire pour le skill (copyright de obra/superpowers) et pour la commande (auteur d'origine à retrouver ; sinon licence du dépôt aitmpl seulement).

## Ce qui reste avant l'essai

1. Tu choisis pour chaque composant : valider, changer de candidat ou laisser de côté (surtout la commande).
2. Tu complètes les licences (copyright lu à la source).
3. Je rebuild, vérifie, affiche l'aperçu exact, puis j'installe sur un projet jetable, relance pour vérifier l'absence de duplication et teste le retour arrière.
