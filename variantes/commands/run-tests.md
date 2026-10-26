---
description: Détecte et exécute la commande de test du projet, puis rapporte résultats, échecs et limites.
allowed-tools: Read, Glob, Grep, Bash
---
<!-- Variante ZakiOS (brouillon), contenu original. -->
Applique le Socle ZakiOS (`.claude/socle/REGLES.md`). Première ligne : `ZAKIOS-SOCLE v1 · PDCA`.

1. **Planifier** : trouve la commande de test déjà définie (`package.json` scripts.test, `Makefile`, `pyproject.toml`, `tox.ini`, README). Si aucune : arrête-toi et dis-le.
2. **Exécuter** : lance **cette commande seulement**. N'installe aucune dépendance, ne modifie aucun code, ne mets à jour aucun snapshot : ce sont des actions séparées à demander.
3. **Vérifier** : rapporte commande, code de sortie, nombre de réussites/échecs, échecs détaillés (test, message).
4. **Agir** : transmets les échecs pour correction. Ne dis « validé » que si la commande a réussi ; liste les contrôles absents (lint, types, couverture) comme non exécutés.
