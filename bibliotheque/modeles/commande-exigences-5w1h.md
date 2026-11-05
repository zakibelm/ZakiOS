---
description: Transforme une idée en exigences structurées (qui, quoi, quand, où, pourquoi, comment) puis en critères d'acceptation vérifiables, en lecture seule.
argument-hint: <idée ou besoin à clarifier>
allowed-tools: Read, Glob, Grep
---
<!-- Modèle ZakiOS (brouillon), contenu original. En amont de plan-writer : clarifier le besoin avant de planifier. -->
Applique le Socle ZakiOS (`.claude/socle/REGLES.md`). Première ligne : `ZAKIOS-SOCLE v1 · PDCA`.

Besoin : $ARGUMENTS

1. **Planifier** : lis le projet si utile (Read, Glob, Grep). Tu ne modifies rien et n'as pas Bash.
2. **Exécuter** : remplis le tableau `Question · Réponse · Source (dite par la personne / vue dans le projet / hypothèse)` :
   - **Qui** : utilisateurs, décideurs, personnes touchées.
   - **Quoi** : résultat attendu, hors périmètre.
   - **Quand** : échéance, fréquence, ordre.
   - **Où** : environnement, appareils, données concernées.
   - **Pourquoi** : problème à résoudre, bénéfice attendu.
   - **Comment** : contraintes techniques, légales (Loi 25, CASL si données personnelles ou envois), budget en $ CAD.
3. **Vérifier** : écris des critères d'acceptation C1, C2… chacun mesurable et relié à une preuve (commande, test, fichier). Marque « non vérifiable » tout critère sans moyen de preuve.
4. **Agir** : liste au plus 5 questions ouvertes à poser à la personne, une ligne chacune, terminée par « ? ». N'invente pas de réponse : une case sans source est une **hypothèse**. Termine par « Prêt à planifier » seulement si les critères obligatoires sont tous prouvables.
