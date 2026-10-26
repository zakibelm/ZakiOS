# Activation dans un projet (pilote)

Périmètre : Claude Code CLI, Linux, projet isolé. Le pilote prouve le parcours complet sur des composants **fictifs** ; aucun composant réel n'est installable tant qu'un humain n'a pas validé sa décision et sa licence.

## Parcours

```sh
# 1. choisir : <projet>/.zakios/profile.json  ->  {"components": ["dépôt:chemin", ...]}
python3 -m zakios plan  --project <projet> --sources-root <sources>      # aperçu, n'écrit rien
python3 -m zakios apply --project <projet> --sources-root <sources> --plan-sha <empreinte du plan>
python3 -m zakios rollback --project <projet>                           # annule la dernière installation
```

## Ce qu'un composant doit avoir pour être installé

| Condition | Où elle se règle |
|---|---|
| décision humaine `conserver`, `fusionner` ou `variante`, liée à l'empreinte actuelle | `decisions/validated.json` |
| licence vérifiée (SPDX, vérificateur, commit lu) | `decisions/licenses.json` (par dépôt ou par composant) |
| empreinte complète | calculée au build |
| compatible Linux | `decisions/annotations.json` (`platform`) |
| dépendances sélectionnées, aucun conflit sélectionné | `decisions/annotations.json` (`depends_on`, `conflicts_with`) |
| paquet autonome (aucun fichier hors de son dossier) | calculé au build |
| type installable : agent, commande, skill, hook | |

Le catalogue doit être valide et exact (pas un build expérimental). Le contenu installé est lu **au commit du catalogue** et son empreinte est revérifiée : une modification locale des sources n'entre jamais dans un projet.

## Où les fichiers vont

| Type | Destination |
|---|---|
| agent | `.claude/agents/<nom>.md` |
| commande | `.claude/commands/<nom>.md` |
| skill | `.claude/skills/<nom>/…` (paquet complet, bit exécutable conservé) |
| hook | `.claude/hooks/zakios/<nom>/…` : **copié, jamais activé** (settings.json n'est pas touché) |

## Garanties

- **Aperçu exact :** `plan` liste les fichiers à créer, mettre à jour ou retirer, les refus avec leurs raisons, et une empreinte du plan. `apply --plan-sha` refuse si le plan a changé entre-temps.
- **Tout ou rien :** un seul refus empêche toute écriture.
- **Fichiers du projet protégés :** un fichier existant qui ne vient pas de ZakiOS n'est jamais écrasé ; un fichier installé puis modifié par l'utilisateur n'est ni écrasé, ni retiré. Un fichier créé par ZakiOS l'est sans écrasement (création atomique qui échoue si l'emplacement est pris, même apparu après l'aperçu).
- **Rien ne sort du projet :** toutes les lectures, écritures et suppressions (fichiers installés, sauvegardes, journal, verrou, état) descendent depuis le dossier du projet avec des descripteurs de dossier ouverts sans suivre les liens symboliques (Linux, `O_NOFOLLOW`). Un lien symbolique substitué à un dossier, même après l'aperçu, fait échouer l'opération. `.zakios` lui-même ne peut pas être un lien vers l'extérieur.
- **Réexécution sans duplication :** une deuxième installation identique ne touche aucun fichier et ne crée pas de transaction.
- **Retour arrière :** chaque installation écrit son journal avant d'agir. En cas d'échec, tout est annulé (fichiers créés, versions précédentes restaurées, état `.zakios/lock.json` rétabli). Une installation interrompue brutalement (même par SIGKILL) est détectée sans écriture, puis annulée au lancement suivant **avant** la validation du plan : sinon les fichiers déjà écrits paraîtraient « non gérés ». Si l'utilisateur les a modifiés entre-temps, l'installation est bloquée, le journal passe en `conflict` et les sauvegardes restent.
- **Retour arrière et reprise sans perte :** avant d'annuler (retour arrière explicite, échec ou reprise après interruption), l'état du disque est comparé à ce que ZakiOS avait écrit. Un fichier modifié depuis, ou un fichier retiré puis recréé par l'utilisateur, bloque la restauration : le journal passe en `conflict`, les sauvegardes restent dans `.zakios/journal/<transaction>/`, et l'aperçu suivant l'indique dans ses notes.
- **Un seul installateur à la fois** par projet (verrou).
- **Écritures avant refus :** `plan` n'écrit rien. `apply` commence par la même validation sans écriture : un refus évident ne crée ni `.zakios` ni verrou. Seul un refus apparu sous verrou (cas de concurrence ou reprise après interruption) peut laisser le dossier d'état.

## État du projet

`.zakios/lock.json` : composants installés, commit, empreinte, licence, fichiers et leurs SHA-256. `.zakios/journal/<transaction>/` : journal et sauvegardes.

## Limites

- Le projet lui-même est ouvert tel que l'utilisateur le désigne (un lien symbolique vers le projet est suivi une fois, au départ).
- La comparaison avant restauration d'un fichier **modifié** (mise à jour annulée) et son remplacement ne sont pas un seul geste atomique : une modification faite pendant les millisecondes de l'annulation, sous verrou, peut passer. Les créations et restaurations de fichiers retirés, elles, n'écrasent jamais.
- Linux seulement.
- Non testé sur de vrais composants : aucune décision ni licence réelle n'est encore validée.
- L'activation d'un hook (settings.json) reste manuelle, après audit de son comportement.
- Pas encore de gestion de versions multiples d'un même composant ni de mise à jour sélective.
- Les conflits et dépendances sont ceux que l'humain déclare : le moteur ne les déduit pas.
