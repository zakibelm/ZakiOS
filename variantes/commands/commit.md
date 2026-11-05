---
description: Prépare un commit propre (Conventional Commits) à partir du diff, sans jamais pousser ni réécrire l'historique.
allowed-tools: Read, Glob, Grep, Bash(git status:*), Bash(git diff:*), Bash(git log:*), Bash(git add:*), Bash(git commit:*)
---
<!-- Variante ZakiOS (brouillon), contenu original. -->
Applique le Socle ZakiOS (`.claude/socle/REGLES.md`). Première ligne : `ZAKIOS-SOCLE v1 · PDCA`.

1. **Planifier** : lis `git status --short`, `git diff --cached` et les 8 derniers titres (`git log --oneline -8`) pour reprendre le style du projet. Si rien n'est indexé, désigne les fichiers liés à la tâche en cours ; n'indexe jamais tout par défaut.
2. **Exécuter** : indexe uniquement ces fichiers, puis crée **un** commit. Titre Conventional Commits (`feat:`, `fix:`, `refactor:`, `docs:`, `test:`, `chore:`), 72 caractères maximum, au présent. Corps : le pourquoi plutôt que le quoi.
3. **Vérifier** : relis `git show --stat HEAD` et compare à ce qui était prévu. Signale tout fichier inattendu.
4. **Agir** : interdits dans ce rôle : `git push`, `--amend`, `--no-verify`, `reset`, `rebase`, `checkout --`. Si un hook de commit échoue, rapporte l'erreur et corrige la cause avec la personne ; ne contourne rien.
