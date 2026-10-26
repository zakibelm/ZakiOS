# Revue du lot 1 (projet jetable) — dossiers à valider

Statut : **revue révisée (rév. 2) après audit externe ; rien n'est validé ni installé.** `decisions/validated.json`, `licenses.json` et `annotations.json` sont inchangés. Les extraits JSON ci-dessous sont à copier **seulement si tu valides**.

Catalogue lu : davila7/claude-code-templates au commit `aff83062f3d0e6a882f23e52611d5811539e6047`, génération 0.5.2. Hooks exclus du lot.

## Révision 2 — corrections reçues et vérifiées

| Problème constaté | Action | Bénéfice |
|---|---|---|
| Rév. 1 : les renvois de `writing-plans` étaient présentés comme « facultatifs ». Faux : le texte contient `REQUIRED SUB-SKILL: superpowers:executing-plans` (ligne 36, en-tête de chaque plan, et ligne 116) et `superpowers:subagent-driven-development` (ligne 110). | Dépendances **obligatoires** tant que le texte reste inchangé. Deux voies : fournir `executing-plans` et `subagent-driven-development` (noms sans préfixe `superpowers:` dans le catalogue, donc à vérifier), ou écrire une variante ZakiOS qui retire ces renvois. | Aucun plan produit ne pointe vers un skill absent. |
| Rév. 1 : « la version VoltAgent n'en contient aucun » reposait sur une recherche de termes. Ce n'est pas une preuve d'apport. | Comparaison à refaire procédure contre procédure, puis essai sur un même diff réel. Le tableau ci-dessous parle d'**écarts observés**, pas d'apport démontré. | Décision fondée sur un résultat, pas sur du vocabulaire. |
| Rév. 1 : licence de `writing-plans` « non lue ». | **Vérifiée** dans le clone `obra/superpowers`, commit `2ce8aa15d05bd57213e6f746f953aafb7ded7a8b` : `LICENSE` = MIT, « Copyright (c) 2025 Jesse Vincent ». | Plus rien à recopier à la main pour ce composant. |
| Limite sur cette preuve | Le `writing-plans` actuel de obra/superpowers **diffère** de la copie aitmpl (texte d'introduction, chemin `docs/superpowers/plans/`, étapes ajoutées). La filiation reste donc probable, pas prouvée, tant qu'on n'a pas retrouvé la version amont dont la copie aitmpl est issue. | Attribution exacte, sans affirmer plus que la preuve. |
| « Origine probable VoltAgent » du code-reviewer | Reste une **hypothèse** ; elle n'entre pas dans `licenses.json` comme fait. | Pas de fausse attribution. |

**Recommandation révisée (à valider par toi) :** passer des trois « composants du catalogue » à trois **variantes ZakiOS** cohérentes entre elles :

1. `code-reviewer` ZakiOS — lecture seule (Read, Glob, Grep et Bash limité à `git diff`/`git log`/`git show`), constats avec fichier, ligne, gravité et preuve.
2. `writing-plans` ZakiOS — sans renvoi vers des skills absents, plans dans `docs/plans/`, méthode alignée sur `docs/PROFIL.md`.
3. `run-tests` ZakiOS — détecte la commande de test déjà définie, l'exécute, rapporte résultat, échecs et limites ; installation de dépendances, modification de code et mise à jour de snapshots restent des actions séparées.

`test-coverage` sort du lot 1. Une variante est du **code ZakiOS** : elle dépend du choix de licence que tu dois encore faire, et son attribution amont (MIT, Jesse Vincent pour le skill) est conservée dans l'en-tête.


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
| Écarts observés | Stratégie « diff d'abord », pré-contrôles outillés, contrôles par langage, sortie gravité + recommandation. Observation par lecture, **apport non démontré** : à confirmer procédure contre procédure puis sur un même diff. |

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

**Problème 2 — dépendances obligatoires (corrigé en rév. 2).** Le texte impose `superpowers:executing-plans` et `superpowers:subagent-driven-development`. **Action :** fournir ces skills ou retirer les renvois dans une variante ZakiOS (voir révision 2). **Bénéfice :** aucun plan ne renvoie à un skill absent.

**Problème 3 — licence (vérifiée en rév. 2).** MIT, « Copyright (c) 2025 Jesse Vincent », lu dans obra/superpowers au commit `2ce8aa15…`. La copie aitmpl diffère du texte amont actuel : filiation probable, non prouvée. **Action :** conserver le texte de licence avec la variante. **Bénéfice :** attribution exacte.

**Effet de bord à connaître :** le skill écrit des fichiers sous `docs/plans/` du projet. Sans danger sur un projet jetable.

**Décision proposée (rév. 2) :** `variante` ZakiOS plutôt que `conserver` (voir révision 2) ; l'extrait ci-dessous reste valable seulement si tu préfères garder le texte tel quel avec ses dépendances.

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

**Décision proposée (rév. 2) :** hors du lot 1 ; remplacer par la variante `run-tests` ZakiOS.

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

Pour le skill : MIT, Copyright (c) 2025 Jesse Vincent (obra/superpowers, commit `2ce8aa15d05bd57213e6f746f953aafb7ded7a8b`) ; à enregistrer seulement après ta validation. Pour la commande (auteur d'origine à retrouver ; sinon licence du dépôt aitmpl seulement).

## Ce qui reste avant l'essai

1. Tu choisis pour chaque composant : valider, changer de candidat ou laisser de côté (surtout la commande).
2. Tu complètes les licences (copyright lu à la source).
3. Je rebuild, vérifie, affiche l'aperçu exact, puis j'installe sur un projet jetable, relance pour vérifier l'absence de duplication et teste le retour arrière.
