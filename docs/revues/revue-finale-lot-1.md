# Revue finale du lot 1 — configuration actuelle

Statut : **à valider par toi.** Rien n'est validé, aucune licence enregistrée, rien d'installé dans un vrai projet. `decisions/validated.json`, `licenses.json` et `annotations.json` sont inchangés. L'historique (versions antérieures, essais 1 à 5) reste dans `lot-1.md` et `essai-lot-1.md` ; ce document ne décrit que la version examinée.

## Version examinée

| | |
|---|---|
| Source figée | `zakibelm/ZakiOS` rôle `propre`, commit `f92d53bfbcf653cb2a5b3d942edbf6792f67710d` |
| Moteur / schéma | 0.6.0 / 5, catalogue en mode `exact`, 3 332 composants |
| `registry.json` | sha256 `1232932b2543300df66ec57723747eb7fc0c280a56b6a3329d59bad567c8ba47` |
| Essai sur cette version | `scripts/essai_lot1.py`, 3 passages, tous les critères satisfaits ; preuves `docs/revues/preuves-essai-6/` |
| Plan d'installation d'essai (fictif) | `plan_sha256` 3cffa21fc4948e421704fa2a3c137c5600c2143163b4b878b3c0540552a5fdeb : 5 fichiers |

## Les cinq éléments du lot

| Élément | Identifiant (après `zakibelm/ZakiOS:`) | Empreinte | Rôle |
|---|---|---|---|
| Socle | `socle/REGLES.md` | `7463126762ef11117d66b096a407f2c224a04332c920460b84e97e3883b13422` | PDCA et règles de conduite, portés une seule fois |
| Relecteur | `variantes/agents/code-reviewer.md` | `799b1f5735642a836421bd2e320b50aaa1b9bc0cbfbbab0356e5f7631741d7af` | relit un diff fourni |
| Planificateur (agent) | `variantes/agents/plan-writer.md` | `f7401cc2bbcad04157093ec94dba989267810654c2f7fd9bcca0ebc6f7a7e157` | retourne un plan |
| Planificateur (méthode) | `variantes/skills/writing-plans/SKILL.md` | `a90075ec5f80214e997cf9bffa3974bb0bb0f7181998e61776adadcb7e143903` | méthode et format du plan |
| Livraison | `zakios/deliver.py`, commande `save-plan` | (code du moteur, testé) | enregistrement contrôlé |

Hors lot : `variantes/commands/run-tests.md` (empreinte `e7c26b2d…8858`). Il reste en brouillon tant que l'environnement isolé n'existe pas.

## 1. Socle

- **Contenu** : PDCA ; fait / hypothèse / preuve ; attendu / vérifié ; jamais de validation annoncée sans contrôle exécuté ; solution inconnue ⇒ investigation suivante ; Problème → Action → Résultat ; montants en $ CAD ; le Socle encadre la mission d'un agent sans retirer à la personne le contrôle de son système.
- **Mécanisme de chargement** : `.claude/CLAUDE.md` contenant `@socle/REGLES.md`, installé avec `.claude/socle/REGLES.md`. Le `CLAUDE.md` de la racine n'est jamais touché ; si `.claude/CLAUDE.md` existe, le Socle est refusé sans rien écraser.
- **Preuve** : avec le canari (présent seulement dans le Socle), 3 passages sur 3 : présent avec le Socle complet, présent avec l'import seul, **absent** sans import ni renvoi (même diff, sessions neuves). Valable pour ce modèle (`claude-sonnet-5-5`) et ce scénario.
- **Réserve** : décision `behavior_audit_required` par construction (il change la conduite de tous les agents). Ta lecture du texte est une revue de son contenu ; elle ne remplace pas les essais de comportement, documentés séparément.

## 2. Relecteur

- **Contenu** : relit un diff **fourni comme donnée**, juge chaque critère d'acceptation (satisfait / non satisfait / non vérifiable) avec preuve, constats `fichier:ligne · gravité · Problème → Action → Résultat · preuve`, recommandation et contrôles non exécutés. Dans son rôle, il ne modifie pas les fichiers et dit qui peut changer ce rôle.
- **Permissions** : `Read, Glob, Grep`. Mesurées à l'initialisation dans les 9 exécutions du relecteur de l'essai 6 (3 passages × 3 variantes). Aucun outil modifiant utilisé, aucun fichier créé, modifié ou supprimé.
- **Scénarios** : défauts connus trouvés (remise sans `/100`, injection SQL) 9/9 ; consigne contradictoire refusée 3/3.
- **Portée à ne pas dépasser** : relecture de **code**. Il n'est pas démontré pour relire un plan (voir « Prochain jalon »).

## 3. Planificateur

- **Contenu** : l'agent lit le skill, lit le projet, retourne un plan PDCA dans un bloc délimité (`=== DEBUT DU PLAN ZAKIOS ===` … `=== FIN DU PLAN ZAKIOS ===`, titre `# `) précédé de `Chemin proposé : docs/plans/….md`. Il n'écrit rien.
- **Permissions** : `Read, Glob, Grep` (mesurées, 3/3), aucun fichier changé.
- **Dépendance** : `plan-writer` → `writing-plans` (il le lit explicitement ; le préchargement `skills:` n'est pas démontré et n'est pas utilisé). À déclarer dans `annotations.json` avant toute installation réelle (extrait ci-dessous).
- **Grille** (présence seulement) : sections Planifier / Exécuter / Vérifier / Agir en titres, critères, preuve, action corrective : satisfaite 3/3.

## 4. Livraison

- **Aperçu** : `save-plan --preview` affiche chemin, octets, `content_sha256` et `delivery_sha256` (format, chemin, contenu, mission) ; n'écrit rien.
- **Enregistrement** : exige le `delivery_sha256` de l'aperçu ; uniquement `docs/plans/**/*.md` ; refuse chemins absolus, `..`, liens symboliques, plan vide ou binaire ; création atomique sans remplacement ; contenu identique ⇒ « déjà enregistré » sans écriture ; contenu différent ⇒ refus.
- **Trace** : une par livraison (`.zakios/deliverables/<delivery_sha256>.json`), jamais réécrite, vérifiée si elle existe.
- **Preuves** : 20 tests (concurrence, interruption, liens symboliques, 4 cas d'identité, 8 refus d'extraction), 2 mutations détectées ; essai de bout en bout 3/3 (`enregistre` puis `deja_enregistre`).

## Décisions proposées (à copier seulement si tu valides)

Chaque validation est liée à l'empreinte ci-dessus : si le contenu change, elle devient périmée.

```json
// decisions/validated.json
{
 "zakibelm/ZakiOS:socle/REGLES.md": {"validated": "conserver", "validated_by": "<ton nom>", "validated_on": "<date>",
  "justification": "règles communes ZakiOS ; chargement prouvé par témoin", "fingerprint_sha256": "7463126762ef11117d66b096a407f2c224a04332c920460b84e97e3883b13422"},
 "zakibelm/ZakiOS:variantes/agents/code-reviewer.md": {"validated": "conserver", "validated_by": "<ton nom>", "validated_on": "<date>",
  "justification": "relecteur de code en lecture seule", "fingerprint_sha256": "799b1f5735642a836421bd2e320b50aaa1b9bc0cbfbbab0356e5f7631741d7af"},
 "zakibelm/ZakiOS:variantes/agents/plan-writer.md": {"validated": "conserver", "validated_by": "<ton nom>", "validated_on": "<date>",
  "justification": "planificateur en lecture seule", "fingerprint_sha256": "f7401cc2bbcad04157093ec94dba989267810654c2f7fd9bcca0ebc6f7a7e157"},
 "zakibelm/ZakiOS:variantes/skills/writing-plans/SKILL.md": {"validated": "conserver", "validated_by": "<ton nom>", "validated_on": "<date>",
  "justification": "méthode de plan PDCA", "fingerprint_sha256": "a90075ec5f80214e997cf9bffa3974bb0bb0f7181998e61776adadcb7e143903"}
}
```

```json
// decisions/annotations.json
{"zakibelm/ZakiOS:variantes/agents/plan-writer.md": {"depends_on": ["zakibelm/ZakiOS:variantes/skills/writing-plans/SKILL.md"]},
 "zakibelm/ZakiOS:variantes/agents/code-reviewer.md": {"variant_of": ["davila7/claude-code-templates:cli-tool/components/agents/development-tools/code-reviewer.md"]}}
```

Ces trois extraits ont été chargés par le moteur dans un dossier temporaire (avec un SPDX d'essai) : 4 décisions valides, aucune périmée, dépendance et variante reconnues. Le Socle n'a pas de dépendance déclarée : son installation est choisie dans la sélection du projet.

## Licences : preuves et incertitudes

| Composant | Ce qui est établi | Incertitude |
|---|---|---|
| Relecteur | Dérivé d'une inspiration : `code-reviewer` d'aitmpl, dépôt **MIT, Copyright Daniel (San) Ávila** (LICENSE lu). Observation : une mesure sommaire de ressemblance textuelle donne 0,03 ; elle n'a aucune portée juridique et ne dit rien des droits ni de la filiation | l'origine amont probable (VoltAgent, MIT, LICENSE lu) reste une hypothèse ; attribution conservée par prudence |
| Skill | Adapté de `writing-plans` d'aitmpl, issu probablement d'**obra/superpowers : MIT, Copyright (c) 2025 Jesse Vincent** (LICENSE lu au commit `2ce8aa15d05bd57213e6f746f953aafb7ded7a8b`). Observation sommaire de ressemblance : 0,03 à 0,05, sans portée juridique | la copie aitmpl diffère du texte amont actuel : filiation exacte non prouvée |
| Socle, plan-writer, run-tests | Contenu original ZakiOS | **la licence du code de ZakiOS n'est pas choisie** |

Une licence enregistrée au niveau du dépôt vaudrait aussi pour `run-tests`, hors lot : sans décision validée, il reste non installable. Une entrée de `licenses.json` exige un SPDX, un vérificateur et le commit de la source : il faut donc **ta licence** avant de l'enregistrer, et **mettre à jour le commit chaque fois que la source est re-figée**.

```json
// decisions/licenses.json — modèle, à compléter après ton choix de licence
{"zakibelm/ZakiOS": {"spdx": "<licence choisie>", "verified_by": "<ton nom>", "verified_on": "<date>",
  "commit": "f92d53bfbcf653cb2a5b3d942edbf6792f67710d",
  "attribution": "ZakiOS (original) ; relecteur inspiré d'aitmpl (MIT, Daniel (San) Ávila) ; skill adapté d'obra/superpowers (MIT, Jesse Vincent)"}}
```

## Ce qui n'est pas démontré

- **Délégation entre agents** : les deux agents fonctionnent séparément ; le script pilote leurs appels. Aucune coordination n'est prouvée.
- Un seul modèle, 3 passages, mode non interactif ; mode interactif non testé.
- `run-tests` et l'écriture isolée : attendent l'isolation.
- Grilles de contenu : présence uniquement, pas la qualité.
- OpenRouter, OmniRoute, séparation par utilisateur, recherche catalogue/Web : cible (`docs/CIBLE.md`).

## Prochain jalon proposé

Demande unique → coordination → planificateur → **revue du plan** → correction éventuelle → aperçu → enregistrement contrôlé.

- Le relecteur actuel juge du code ; il faut une **mission de revue de plan** (faisabilité, couverture du besoin, critères, vérifications, actions correctives), sans supposer que son rôle actuel suffit.
- Un identifiant de **mission** relie les passages ; les traces portent les empreintes de chaque livrable.
- Un seul modèle au début ; OpenRouter / OmniRoute et `run-tests` isolé ensuite.
- Critère de réussite : le plan enregistré a été relu, les écarts relevés ont été corrigés ou explicitement acceptés, et la trace relie demande, plan, relecture et livraison.

## Ce que j'attends de toi

1. Validation ou refus de chacun des quatre éléments (Socle, relecteur, plan-writer, skill) après lecture de leur texte.
2. Ton choix de licence pour le code de ZakiOS.
3. Ton accord pour le jalon de coordination.
