---
description: Audite le budget de contexte d'un projet (CLAUDE.md, skills, MCP, hooks) et propose où déplacer chaque règle, en lecture seule.
allowed-tools: Read, Glob, Grep
---
<!-- Variante ZakiOS (brouillon), contenu original. Critères issus de docs/PRATIQUES.md, section 1 (à confirmer par essai). -->
Applique le Socle ZakiOS (`.claude/socle/REGLES.md`). Première ligne : `ZAKIOS-SOCLE v1 · PDCA`.

1. **Planifier** : repère `CLAUDE.md` (et ses imports `@…`), `.claude/skills/*/SKILL.md`, `.mcp.json`, `.claude/settings*.json`. Tu ne modifies rien et n'as pas Bash.
2. **Exécuter** : relève (a) la taille de chaque CLAUDE.md et de ses imports, avec le repère de 500 lignes ; (b) le nombre de skills et la longueur de chaque description (toujours chargée) ; (c) le nombre de serveurs MCP (coût permanent) ; (d) les règles de CLAUDE.md qui sont des références longues, des règles souvent violées ou des consignes déjà déduites du code.
3. **Vérifier** : un tableau `élément · mécanisme actuel · coût de contexte (toujours / à la demande / nul) · verdict (à garder / à déplacer / à supprimer)`, avec le fichier et la ligne comme preuve. Distingue ce que tu as **mesuré** de ce que tu **supposes**.
4. **Agir** : pour chaque élément à déplacer, énonce Problème → Action → Résultat (ex. « référence longue dans CLAUDE.md → la mettre dans un skill → contexte libéré »). Demande à la personne de lancer `/mcp` et `/context` pour le coût réel par serveur : tu ne peux pas les exécuter. Liste ces contrôles comme non exécutés.
