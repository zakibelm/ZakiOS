---
description: Vérifie une interface web locale avec le MCP Playwright (rendu, console, parcours) et rapporte preuves et limites.
argument-hint: <URL locale, ex. http://localhost:3000/page>
allowed-tools: Read, Glob, Grep, Bash, mcp__playwright__*
---
<!-- Variante ZakiOS (brouillon), contenu original. Dépend du MCP Playwright : sans lui, la variante s'arrête. -->
Applique le Socle ZakiOS (`.claude/socle/REGLES.md`). Première ligne : `ZAKIOS-SOCLE v1 · PDCA`.

URL : $ARGUMENTS

1. **Planifier** : lis les critères d'acceptation fournis (sinon demande-les) et garde ceux qui touchent l'interface. Vérifie que les outils `mcp__playwright__*` existent ; sinon arrête-toi et dis « non vérifié : MCP Playwright indisponible ». Trouve la commande de démarrage du serveur de dev déjà définie dans le projet (README, `package.json`) ; n'en invente pas.
2. **Exécuter** : si le serveur ne répond pas, lance **seulement** cette commande, en arrière-plan. N'installe rien, ne modifie aucun fichier du projet. Ouvre l'URL, capture l'écran en 1280 px puis en 390 px, lis la console et les requêtes réseau en erreur, puis parcours chaque critère en agissant réellement sur la page.
3. **Vérifier** : un tableau `critère · résultat (satisfait / non satisfait / non vérifiable) · preuve (capture, message de console, requête)`. Distingue ce que tu as **vu** de ce que tu **supposes**.
4. **Agir** : pour chaque critère non satisfait, énonce Problème → Action → Résultat attendu et transmets la correction à la personne ou à un autre agent : tu ne la fais pas. Ne dis « validé » que si tous les critères sont satisfaits ; liste les contrôles non exécutés (accessibilité, autres navigateurs, états d'erreur).
