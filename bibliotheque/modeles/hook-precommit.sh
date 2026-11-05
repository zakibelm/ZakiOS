#!/usr/bin/env bash
# Modèle ZakiOS (brouillon, contenu original) : contre-pression au moment du commit.
# Quand un agent exécute `git commit`, ce script rejoue les contrôles du projet ; s'il échoue, le commit est refusé
# et l'agent voit l'erreur et se corrige. Les mêmes contrôles valent pour les humains et pour les agents.
#
# Installation : copier vers .git/hooks/pre-commit (chmod +x) ou l'appeler depuis votre gestionnaire de hooks.
# Réglage : ZAKIOS_PRECOMMIT_CMDS = commandes séparées par « ; » (défaut : tests puis verify de ZakiOS).
# Un hook n'est jamais validé par un score : audit par comportement obligatoire (docs/GRILLE-AUDIT-HOOKS.md).
set -u

CMDS="${ZAKIOS_PRECOMMIT_CMDS:-python3 -m unittest discover -s tests -t .;python3 -m zakios verify}"

IFS=';' read -r -a LISTE <<< "$CMDS"
for cmd in "${LISTE[@]}"; do
  [ -z "${cmd// /}" ] && continue
  if ! bash -c "$cmd"; then
    code=$?
    echo "Commit refusé : « $cmd » a échoué (code $code)." >&2
    echo "Action : corriger la cause puis recommencer ; ne pas contourner le contrôle." >&2
    exit 1
  fi
done
exit 0
