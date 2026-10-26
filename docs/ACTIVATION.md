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
- **Fichiers du projet protégés :** un fichier existant qui ne vient pas de ZakiOS n'est jamais écrasé ; un fichier installé puis modifié par l'utilisateur n'est ni écrasé, ni retiré, ni supprimé par un retour arrière. Un lien symbolique qui sortirait du projet est refusé.
- **Réexécution sans duplication :** une deuxième installation identique ne touche aucun fichier et ne crée pas de transaction.
- **Retour arrière :** chaque installation écrit son journal avant d'agir. En cas d'échec, tout est annulé (fichiers créés, versions précédentes restaurées, état `.zakios/lock.json` rétabli). Une installation interrompue brutalement est annulée au lancement suivant.
- **Un seul installateur à la fois** par projet (verrou).

## État du projet

`.zakios/lock.json` : composants installés, commit, empreinte, licence, fichiers et leurs SHA-256. `.zakios/journal/<transaction>/` : journal et sauvegardes.

## Limites

- Non testé sur de vrais composants : aucune décision ni licence réelle n'est encore validée.
- L'activation d'un hook (settings.json) reste manuelle, après audit de son comportement.
- Pas encore de gestion de versions multiples d'un même composant ni de mise à jour sélective.
- Les conflits et dépendances sont ceux que l'humain déclare : le moteur ne les déduit pas.
